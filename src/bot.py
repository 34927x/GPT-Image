"""
Telegram Bot v2 — Full menu, buttons, progress, bulk, TXT, auto-detect
"""

import asyncio, io, json as jmod, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters, ContextTypes)

import config
from db import init_db
from models import Account, Queue
from accounts.manager import (is_admin, export_accounts, import_accounts,
                              get_session_status, mark_expired)
from worker import submit_prompt, close as close_worker, check_session

# Semaphore: only one queue processing at a time
queue_semaphore = asyncio.Semaphore(1)

# ── Keyboards ──

def main_menu():
    kb = [
        [InlineKeyboardButton("🖼️ Generate Image", callback_data="gen")],
        [InlineKeyboardButton("📋 My Queue", callback_data="myqueue"),
         InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("👤 Accounts", callback_data="accounts"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    return InlineKeyboardMarkup(kb)

def admin_menu():
    kb = [
        [InlineKeyboardButton("📦 Export Accounts", callback_data="export")],
        [InlineKeyboardButton("📥 Import Accounts", callback_data="import_prompt")],
        [InlineKeyboardButton("🔄 Check Sessions", callback_data="check_sessions")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(kb)

def size_menu():
    kb = [
        [
            InlineKeyboardButton("1:1 Square", callback_data="size_1:1"),
            InlineKeyboardButton("16:9 Wide", callback_data="size_16:9"),
        ],
        [
            InlineKeyboardButton("9:16 Portrait", callback_data="size_9:16"),
            InlineKeyboardButton("4:3 Standard", callback_data="size_4:3"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(kb)

def bulk_menu(prompt, image_size):
    kb = [
        [InlineKeyboardButton("1", callback_data=f"bulk_{prompt[:50]}_{image_size}_1"),
         InlineKeyboardButton("2", callback_data=f"bulk_{prompt[:50]}_{image_size}_2"),
         InlineKeyboardButton("4", callback_data=f"bulk_{prompt[:50]}_{image_size}_4")],
        [InlineKeyboardButton("🔙 Back", callback_data="gen")],
    ]
    return InlineKeyboardMarkup(kb)

# ── Handlers ──

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *GPT Image Bot*\n\n"
        "Simply send me any text — I'll auto-generate an image!\n"
        "Or use /menu for more options.\n\n"
        "_Made by TurabCoder_"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📌 *Menu*", parse_mode="Markdown", reply_markup=main_menu())

# ── Auto-detect: any text = prompt ──

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Check if user is in a flow
    ud = context.user_data

    if ud.get("awaiting_import"):
        # In import flow — wait for file, not text
        await update.message.reply_text("Please send a .json file for import")
        return

    if ud.get("awaiting_size"):
        # They sent text but we asked for size — ask them to use buttons
        await update.message.reply_text("Please select image size using the buttons below 👇", reply_markup=size_menu())
        return

    if ud.get("awaiting_bulk"):
        # Already asked bulk — send buttons
        prompt = ud.get("pending_prompt", text)
        image_size = ud.get("pending_size", "1:1")
        await update.message.reply_text(
            f"Prompt: `{prompt[:50]}`\nSize: {image_size}\n\nHow many images?",
            parse_mode="Markdown",
            reply_markup=bulk_menu(prompt, image_size)
        )
        return

    # Auto-detect: any non-command text = generation request
    ud["pending_prompt"] = text
    ud["awaiting_size"] = True

    await update.message.reply_text(
        f"🖼️ *Image Size?*\n\nPrompt: `{text[:100]}`\n\nChoose aspect ratio:",
        parse_mode="Markdown",
        reply_markup=size_menu()
    )

# ── Gen command ──

async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text(
            "Send any text — I'll auto-generate!\nOr: /gen <prompt>",
            reply_markup=main_menu()
        )
        return
    context.user_data["pending_prompt"] = prompt
    context.user_data["awaiting_size"] = True
    await update.message.reply_text(
        f"🖼️ *Image Size?*\n\nPrompt: `{prompt[:100]}`",
        parse_mode="Markdown",
        reply_markup=size_menu()
    )

# ── File handler (TXT prompts + JSON import) ──

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document

    if doc.file_name.endswith(".json") and is_admin(user_id):
        # Admin JSON import
        file = await doc.get_file()
        content = await file.download_as_bytearray()
        try:
            data = jmod.loads(content)
            count = import_accounts(data)
            await update.message.reply_text(f"✅ Imported {count} accounts", reply_markup=main_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ Import error: {e}")
        return

    if doc.file_name.endswith(".txt"):
        # Bulk prompts from TXT file
        file = await doc.get_file()
        content = (await file.download_as_bytearray()).decode("utf-8", errors="replace")
        prompts = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
        if not prompts:
            await update.message.reply_text("❌ No prompts found in file (separate by blank line)")
            return

        # Save prompts to user_data for size selection
        context.user_data["pending_bulk_file"] = prompts
        context.user_data["awaiting_size"] = True
        context.user_data["file_upload_mode"] = True
        await update.message.reply_text(
            f"📄 Found {len(prompts)} prompts from file.\n\n"
            f"First: `{prompts[0][:50]}`\n\n"
            "Choose image size for ALL prompts:",
            parse_mode="Markdown",
            reply_markup=size_menu()
        )
        return

    await update.message.reply_text("Send a .txt file with prompts (blank line = separator) or .json for import")

# ── Button handler ──

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    is_adm = is_admin(user_id)
    ud = context.user_data

    # ── Size selection ──
    if data.startswith("size_"):
        image_size = data.split("_", 1)[1]
        ud["pending_size"] = image_size
        ud["awaiting_size"] = False

        prompt = ud.get("pending_prompt", "")
        if not prompt and ud.get("pending_bulk_file"):
            # From file upload — add all with this size
            prompts = ud.pop("pending_bulk_file", [])
            image_size = ud.get("pending_size", "1:1")
            count = 0
            for p in prompts:
                Queue.add(p, user_id, image_size=image_size, bulk_count=1)
                count += 1
            ud.pop("file_upload_mode", None)
            ud.pop("pending_size", None)
            await query.edit_message_text(
                f"📥 Added {count} prompts from file!\n"
                f"Size: {image_size}\n\n"
                f"⏳ Position in queue: #{Queue.get_pending_count()}",
                reply_markup=main_menu()
            )
            asyncio.create_task(process_queue())
            return

        if not prompt:
            await query.edit_message_text("❌ No prompt found. Send text again.", reply_markup=main_menu())
            return

        # Ask bulk count
        ud["awaiting_bulk"] = True
        await query.edit_message_text(
            f"Prompt: `{prompt[:50]}`\nSize: {image_size}\n\nHow many images?",
            parse_mode="Markdown",
            reply_markup=bulk_menu(prompt, image_size)
        )
        return

    # ── Bulk count selection ──
    if data.startswith("bulk_"):
        parts = data.split("_", 3)
        # bulk_{prompt[:50]}_{image_size}_{count}
        if len(parts) >= 4:
            prompt_trunc = parts[1]
            image_size = parts[2]
            bulk_count = int(parts[3])
        else:
            await query.edit_message_text("❌ Error parsing bulk data", reply_markup=main_menu())
            return

        # Retrieve full prompt from user_data
        prompt = ud.get("pending_prompt", prompt_trunc)
        ud["awaiting_bulk"] = False
        ud.pop("pending_prompt", None)
        ud.pop("pending_size", None)

        Queue.add(prompt, user_id, image_size=image_size, bulk_count=bulk_count)

        pending = Queue.get_pending_count()
        await query.edit_message_text(
            f"✅ *Queued!*\n\n"
            f"Prompt: `{prompt[:50]}`\n"
            f"Size: {image_size}\n"
            f"Count: {bulk_count}\n"
            f"Position: #{pending}\n\n"
            f"I'll send images here as they're ready!",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

        asyncio.create_task(process_queue())
        return

    # ── Other menu items ──

    if data == "gen":
        ud["awaiting_prompt"] = True
        await query.edit_message_text(
            "Send me any text — I'll auto-generate an image!\n"
            "Or upload a .txt file with prompts.",
            reply_markup=main_menu()
        )
        return

    if data == "myqueue":
        items = Queue.get_user_queue(user_id)
        if not items:
            await query.edit_message_text("📋 Your queue is empty!", reply_markup=main_menu())
            return
        icon = {"pending": "⏳", "processing": "🔄", "done": "✅", "fail": "❌"}
        lines = ["📋 *Your Queue:*"]
        for i, item in enumerate(items[-15:]):
            si = icon.get(item["status"], "❓")
            p = item["prompt"][:30]
            batch = f" ({item.get('batch_index',0)+1}/{item.get('batch_total',1)})" if item.get('batch_total',1) > 1 else ""
            lines.append(f"{i+1}. {si} `{p}`{batch}")
        lines.append(f"\n*Total:* {len(items)}")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=main_menu())
        return

    if data == "status":
        qs = Queue.stats()
        ac = Account.count()
        ses = get_session_status()
        text = (
            f"📊 *Status*\n"
            f"👤 Accounts: {ac}\n"
            f"⏳ Pending: {qs['pending']}\n"
            f"🔄 Processing: {qs.get('processing',0)}\n"
            f"✅ Done: {qs['done']}\n"
            f"❌ Failed: {qs['fail']}\n\n"
            f"*Sessions:*\n" + "\n".join(ses[:5])
        )
        kb = [[InlineKeyboardButton("🔄 Refresh", callback_data="status"),
               InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "accounts":
        docs = Account.get_all()
        if not docs:
            await query.edit_message_text("No accounts. Admin can import or use extension.", reply_markup=main_menu())
            return
        lines = ["👤 *Accounts:*"]
        for i, d in enumerate(docs[:10]):
            c = len(d.get("cookies", []))
            l = d.get("label", f"#{i+1}")
            exp = "❌" if d.get("expired") else "✅"
            src = "🌐" if d.get("source") == "extension" else "📦"
            lines.append(f"{src}{exp} {i+1}. `{l}` ({c}ck)")
        if len(docs) > 10:
            lines.append(f"\n...and {len(docs)-10} more")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=main_menu())
        return

    if data == "help":
        txt = (
            "🤖 *GPT Bot Help*\n\n"
            "• Send *any text* — auto-generates image\n"
            "• Upload *.txt file* — bulk prompts\n"
            "• /menu — Full menu\n"
            "• /status — Bot + queue status\n\n"
            "_Made by TurabCoder_"
        )
        await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu())
        return

    # ── Admin ──

    if data == "admin" and is_adm:
        await query.edit_message_text("⚙️ *Admin Panel*", parse_mode="Markdown", reply_markup=admin_menu())
        return

    if data == "export" and is_adm:
        data_list = export_accounts()
        if not data_list:
            await query.edit_message_text("Nothing to export", reply_markup=admin_menu())
            return
        bio = io.BytesIO(jmod.dumps(data_list, indent=2, default=str).encode())
        bio.name = "gpt-accounts.json"
        await query.message.reply_document(bio, caption="📦 Accounts export")
        await query.edit_message_text("✅ Exported", reply_markup=admin_menu())
        return

    if data == "import_prompt" and is_adm:
        context.user_data["awaiting_import"] = True
        await query.edit_message_text("Send me the .json accounts file.", reply_markup=admin_menu())
        return

    if data == "check_sessions" and is_adm:
        await query.edit_message_text("🔄 Checking sessions...")
        result = await check_session()
        ses = get_session_status()
        text = "✅ *Session Check Complete*\n\n" + "\n".join(ses)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_menu())
        return

    if data == "back_main":
        await query.edit_message_text("📌 *Menu*", parse_mode="Markdown", reply_markup=main_menu())
        return

# ── Queue Processor (with live progress) ──

async def process_queue():
    async with queue_semaphore:
        while True:
            item = Queue.get_pending()
            if not item:
                break

            qid = item["_id"]
            prompt = item["prompt"]
            user_id = item["user_id"]
            batch_idx = item.get("batch_index", 0)
            batch_total = item.get("batch_total", 1)
            image_size = item.get("image_size", "1:1")

            Queue.update_status(qid, Queue.STATUS_PROCESSING)

            # Send progress message (will be edited)
            progress_msg = None
            try:
                from telegram import Bot
                bot = Bot(config.BOT_TOKEN)
                batch_info = f" ({batch_idx+1}/{batch_total})" if batch_total > 1 else ""
                progress_msg = await bot.send_message(
                    chat_id=user_id,
                    text=f"🔄 Generating: `{prompt[:40]}`{batch_info}\n⏳ Starting...",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

            async def progress_callback(msg: str):
                nonlocal progress_msg
                if progress_msg:
                    try:
                        batch_info = f" ({batch_idx+1}/{batch_total})" if batch_total > 1 else ""
                        text = f"🖼️ `{prompt[:40]}`{batch_info}\n{msg}"
                        await progress_msg.edit_text(text, parse_mode="Markdown")
                    except Exception:
                        pass

            result = await submit_prompt(
                prompt,
                image_size=image_size,
                progress_callback=progress_callback
            )

            if result.get("success") and result.get("image_url"):
                Queue.update_status(qid, Queue.STATUS_DONE, image_url=result["image_url"])
                await send_image_to_user(item, result["image_url"], progress_msg)
            else:
                err = result.get("error", "Unknown error")[:100]
                Queue.update_status(qid, Queue.STATUS_FAIL, error=err)
                if progress_msg:
                    try:
                        await progress_msg.edit_text(f"❌ `{prompt[:40]}` — {err}", parse_mode="Markdown")
                    except Exception:
                        pass

            await asyncio.sleep(2)

async def send_image_to_user(item, image_url, progress_msg=None):
    """Download image from URL and send to user. Falls back to URL text."""
    from telegram import Bot
    bot = Bot(config.BOT_TOKEN)
    user_id = item["user_id"]
    prompt = item["prompt"]
    batch_idx = item.get("batch_index", 0)
    batch_total = item.get("batch_total", 1)

    try:
        import requests
        resp = requests.get(image_url, timeout=30)
        if resp.status_code == 200:
            bio = io.BytesIO(resp.content)
            from utils.helpers import make_image_filename
            bio.name = make_image_filename(prompt)

            batch_tag = f" ({batch_idx+1}/{batch_total})" if batch_total > 1 else ""
            caption = f"✅ *{prompt[:100]}*{batch_tag}\n\n_By @TurabCoder_"

            await bot.send_photo(
                chat_id=user_id,
                photo=bio,
                caption=caption,
                parse_mode="Markdown"
            )

            if progress_msg:
                try:
                    await progress_msg.delete()
                except Exception:
                    pass
            return
    except Exception as e:
        print(f"[bot] Send image error: {e}")

    # Fallback: send URL as text
    if progress_msg:
        try:
            await progress_msg.edit_text(
                f"✅ `{prompt[:50]}`\n{image_url}",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"✅ `{prompt[:50]}`\n{image_url}",
                parse_mode="Markdown"
            )
        except Exception:
            pass

async def status_command(update, context):
    qs = Queue.stats()
    ac = Account.count()
    await update.message.reply_text(
        f"📊 *Status*\n👤 Accounts: {ac}\n⏳ Pending: {qs['pending']}\n"
        f"🔄 Processing: {qs.get('processing',0)}\n✅ Done: {qs['done']}\n❌ Failed: {qs['fail']}",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
