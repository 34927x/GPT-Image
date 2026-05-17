import asyncio, io, json as jmod, re
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters, ContextTypes)

import config
from db import init_db
from models import Account, Queue
from accounts.manager import (is_admin, export_accounts, import_accounts,
                              get_session_status, mark_expired, add_manual_account,
                              reset_limited_accounts, parse_limit_reset_time)
from worker import submit_prompt, submit_bulk, check_session
from ui import (box, error_box, menu_header, queue_box, progress_box,
                result_box, status_box, accounts_box, queued_box, help_box,
                image_caption, center, SEP, END)

queue_semaphore = asyncio.Semaphore(1)

async def safe_edit(msg, *args, **kwargs):
    """Edit message, silently ignore 'Message is not modified' error."""
    try:
        return await msg.edit_text(*args, **kwargs)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return None
        raise

# ── Keyboards ──

def main_menu(user_id: int = None):
    kb = [
        [InlineKeyboardButton("🎨 Generate Image", callback_data="gen")],
        [InlineKeyboardButton("📋 My Queue", callback_data="myqueue"),
         InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("👥 Accounts", callback_data="accounts"),
         InlineKeyboardButton("📖 Guide", callback_data="help")],
    ]
    if user_id and is_admin(user_id):
        kb.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin")])
    return InlineKeyboardMarkup(kb)

def admin_menu():
    kb = [
        [InlineKeyboardButton("➕ Add Account", callback_data="add_account"),
         InlineKeyboardButton("📦 Export", callback_data="export")],
        [InlineKeyboardButton("📥 Import", callback_data="import_prompt"),
         InlineKeyboardButton("🔄 Check", callback_data="check_sessions")],
        [InlineKeyboardButton("⏰ Reset Limits", callback_data="reset_limits"),
         InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(kb)

def size_menu():
    kb = [
        [InlineKeyboardButton("⬜ 1:1 Square", callback_data="size_1:1"),
         InlineKeyboardButton("🖥️ 16:9 Wide", callback_data="size_16:9")],
        [InlineKeyboardButton("📱 9:16 Phone", callback_data="size_9:16"),
         InlineKeyboardButton("📺 4:3 Classic", callback_data="size_4:3")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(kb)

def bulk_menu(prompt, image_size):
    kb = [
        [InlineKeyboardButton("1️⃣ Single", callback_data=f"b_{image_size}_1"),
         InlineKeyboardButton("2️⃣ Double", callback_data=f"b_{image_size}_2")],
        [InlineKeyboardButton("4️⃣ Quad Pack", callback_data=f"b_{image_size}_4")],
        [InlineKeyboardButton("🔙 Back", callback_data="gen")],
    ]
    return InlineKeyboardMarkup(kb)

# ── Handlers ──

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"{SEP}\n"
        f"{center('🎨 Welcome to GPT Image Bot!')}\n"
        f"{SEP}\n\n"
        f"🚀 *How It Works*\n"
        f"  • 📝 Send any text → AI generates image\n"
        f"  • 📁 Upload `.txt` file → Bulk processing\n"
        f"  • 🖼️ Images delivered right in this chat\n"
        f"  • 🔄 Multi-account auto-failover\n\n"
        f"📋 *Quick Start*\n"
        f"  • ✏️ Just type what you want to see\n"
        f"  • 📐 Choose aspect ratio when prompted\n"
        f"  • 🔢 Select count (1 / 2 / 4 images)\n"
        f"  • ✅ Done! Image will appear here\n\n"
        f"💡 *Tips*\n"
        f"  • 🎨 Be descriptive for best results\n"
        f"  • 📄 Separate prompts by blank line in `.txt`\n"
        f"  • 📊 Use /menu for full options\n\n"
        f"{END}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu(update.effective_user.id))

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(menu_header(), parse_mode="Markdown", reply_markup=main_menu(update.effective_user.id))

# ── Auto-detect: any text = prompt ──

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    ud = context.user_data
    user_id = update.effective_user.id

    if ud.get("awaiting_import"):
        await update.message.reply_text(
            box("📥 Import",
                "━━ 📥 *Send Your JSON File* ━━\n\n"
                "   • 📁 Please upload a `.json` file\n"
                "   • 📋 Format must match export format\n"
                "   • 🔄 I'll import all accounts automatically",
                emoji="📥"),
            parse_mode="Markdown"
        )
        return

    if ud.get("awaiting_account_json"):
        if " | " in txt:
            label, cookies_str = txt.split(" | ", 1)
            label = label.strip()
        else:
            label = None
            cookies_str = txt
        ok, msg = add_manual_account(cookies_str, label)
        if ok:
            ud["awaiting_account_json"] = False
            await update.message.reply_text(
                box("➕ Account Added",
                    "━━ ✅ *Successfully Added* ━━\n\n"
                    f"   • 📝 `{msg}`\n"
                    "   • 🔄 Ready for image generation\n"
                    "   • 🔐 Cookies stored securely\n\n"
                    "━━ 📌 *Next Steps* ━━\n"
                    "   • Check `/status` to see accounts\n"
                    "   • Send any text to generate images",
                    emoji="➕"),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        else:
            await update.message.reply_text(
                error_box("😵‍💫 Account Add Failed!", msg,
                          reasons=["❌ Invalid JSON format detected",
                                   "🍪 Missing or malformed cookies array",
                                   "📋 Copy from extension export for correct format"],
                          tips=["📋 Export existing account to see correct format",
                                 "📸 Capture fresh cookies from chatgpt.com",
                                 "📬 Contact @TurabCoder if problem persists"]),
                parse_mode="Markdown"
            )
        return

    if ud.get("awaiting_size"):
        await update.message.reply_text(
            box("📐 Choose Size",
                "━━ 📐 *Select Aspect Ratio* ━━\n\n"
                "   • Pick the image shape you want\n"
                "   • Use buttons below to choose\n\n"
                "━━ 📌 *Options* ━━\n"
                "   • ⬜ 1:1 → Perfect for social media\n"
                "   • 🖥️ 16:9 → Widescreen / YouTube\n"
                "   • 📱 9:16 → Phone wallpaper / Stories\n"
                "   • 📺 4:3 → Classic photo / Presentations",
                emoji="📐"),
            parse_mode="Markdown",
            reply_markup=size_menu()
        )
        return

    if ud.get("awaiting_bulk"):
        prompt = ud.get("pending_prompt", txt)
        image_size = ud.get("pending_size", "1:1")
        await update.message.reply_text(
            box("🔢 How Many Images?",
                f"━━ 🔢 *Select Image Count* ━━\n\n"
                f"   • ✏️ Prompt: `{prompt[:50]}`\n"
                f"   • 📐 Size: {image_size}\n\n"
                "   Choose how many to generate:",
                emoji="🔢"),
            parse_mode="Markdown",
            reply_markup=bulk_menu(prompt, image_size)
        )
        return

    Queue.add(txt, user_id, image_size="1:1", bulk_count=1)
    await update.message.reply_text(
        queued_box(txt[:50], "1:1", "1️⃣ Single", Queue.get_pending_count()),
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )
    asyncio.create_task(process_queue())

# ── Gen command ──

async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text(
            box("📝 Usage",
                "━━ 📝 *How to Use /gen* ━━\n\n"
                "   • `/gen <your prompt>`\n"
                "   • Example: `/gen a futuristic city`\n\n"
                "━━ 💡 *Or Just Type* ━━\n"
                "   • Send any text directly\n"
                "   • I'll auto-detect and generate!",
                emoji="📝"),
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        return
    user_id = update.effective_user.id
    Queue.add(prompt, user_id, image_size="1:1", bulk_count=1)
    await update.message.reply_text(
        queued_box(prompt[:50], "1:1", "1️⃣ Single", Queue.get_pending_count()),
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )
    asyncio.create_task(process_queue())

# ── File handler (TXT prompts + JSON import) ──

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document

    if doc.file_name.endswith(".json") and is_admin(user_id):
        file = await doc.get_file()
        content = await file.download_as_bytearray()
        try:
            data = jmod.loads(content)
            count = import_accounts(data)
            await update.message.reply_text(
                box("📥 Import Complete",
                    "━━ ✅ *Import Successful* ━━\n\n"
                    f"   • 📥 Imported `{count}` account(s)\n"
                    f"   • 🔄 Ready for image generation\n"
                    f"   • 🏷️ Duplicates auto-renamed\n\n"
                    "━━ 📌 *Status* ━━\n"
                    "   All accounts synced to database",
                    emoji="📥"),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        except Exception as e:
            await update.message.reply_text(
                error_box("😵‍💫 Import Failed!", str(e)[:100],
                          reasons=["❌ Invalid JSON structure",
                                   "📋 File doesn't match export format",
                                   "🔤 Encoding issues detected"],
                          tips=["📦 Export an account first to see format",
                                 "📄 Make sure file is valid JSON",
                                 "📬 Contact @TurabCoder if needed"]),
                parse_mode="Markdown"
            )
        return

    if doc.file_name.endswith(".txt"):
        file = await doc.get_file()
        content = (await file.download_as_bytearray()).decode("utf-8", errors="replace")
        prompts = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
        if not prompts:
            await update.message.reply_text(
                box("📭 Empty File",
                    "━━ 📭 *No Prompts Found* ━━\n\n"
                    "   • 📄 Your `.txt` file is empty\n"
                    "   • 📝 Separate each prompt by blank line\n\n"
                    "━━ ✅ *Example Format* ━━\n"
                    "   `a red sports car`\n"
                    "   `(blank line)`\n"
                    "   `a blue ocean view`",
                    emoji="📭"),
                parse_mode="Markdown"
            )
            return

        context.user_data["pending_bulk_file"] = prompts
        context.user_data["awaiting_size"] = True
        await update.message.reply_text(
            box("📁 File Uploaded",
                "━━ 📁 *File Processed Successfully* ━━\n\n"
                f"   • 📄 Found **{len(prompts)}** prompts\n"
                f"   • 📝 First: `{prompts[0][:50]}`\n\n"
                "━━ 📐 *Choose Image Size* ━━\n"
                "   This size will apply to ALL prompts",
                emoji="📁"),
            parse_mode="Markdown",
            reply_markup=size_menu()
        )
        return

    await update.message.reply_text(
        box("❌ Unsupported File",
            "━━ ❌ *File Type Not Supported* ━━\n\n"
            "   • Send `.txt` for text prompts\n"
            "   • Send `.json` for account import\n\n"
            "━━ 💡 *Need Help?* ━━\n"
            "   Use /menu to see all options",
            emoji="❌"),
        parse_mode="Markdown"
    )

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
            prompts = ud.pop("pending_bulk_file", [])
            image_size = ud.get("pending_size", "1:1")
            Queue.add(prompts, user_id, image_size=image_size)
            ud.pop("pending_size", None)
            await safe_edit(query.message,
                box("✅ Bulk Queued",
                    "━━ ✅ *Bulk Upload Successful* ━━\n\n"
                    f"   • 📥 Added `{len(prompts)}` prompts from file\n"
                    f"   • 📐 Size: `{image_size}`\n"
                    f"   • 🎯 Position: `#{Queue.get_pending_count()}`\n\n"
                    "━━ ⏰ *What Now?* ━━\n"
                    "   • 🔄 Processing all in one session\n"
                    "   • 📬 Each image sent here when ready\n"
                    "   • 📊 Check status anytime",
                    emoji="✅"),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            asyncio.create_task(process_queue())

        if not prompt:
            await safe_edit(query.message,
                box("❌ Error",
                    "━━ ❌ *No Prompt Found* ━━\n\n"
                    "   • 📝 Please send your text again\n"
                    "   • 🔄 I'll restart the process",
                    emoji="❌"),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            return

        ud["awaiting_bulk"] = True
        await safe_edit(query.message,
            box("🔢 How Many Images?",
                f"━━ 🔢 *Select Image Count* ━━\n\n"
                f"   • ✏️ Prompt: `{prompt[:50]}`\n"
                f"   • 📐 Size: {image_size}\n\n"
                "   Choose how many to generate:",
                emoji="🔢"),
            parse_mode="Markdown",
            reply_markup=bulk_menu(prompt, image_size)
        )
        return

    # ── Bulk count selection ──
    if data.startswith("b_"):
        parts = data.split("_")
        if len(parts) >= 3:
            image_size = parts[1]
            bulk_count = int(parts[2])
        else:
            await safe_edit(query.message,
                box("❌ Error",
                    "━━ ❌ *Something went wrong* ━━\n\n"
                    "   • Please start again from /menu",
                    emoji="❌"),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            return

        prompt = ud.get("pending_prompt", "")
        if not prompt:
            await safe_edit(query.message,
                box("❌ Prompt Lost",
                    "━━ ❌ *Prompt Not Found* ━━\n\n"
                    "   • Please send your prompt again\n"
                    "   • Session data was cleared",
                    emoji="❌"),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            return
        ud["awaiting_bulk"] = False
        ud.pop("pending_prompt", None)
        ud.pop("pending_size", None)

        Queue.add(prompt, user_id, image_size=image_size, bulk_count=bulk_count)
        pending = Queue.get_pending_count()

        count_label = {1: "1️⃣ Single", 2: "2️⃣ Double", 4: "4️⃣ Quad"}.get(bulk_count, f"{bulk_count}x")
        await safe_edit(query.message,
            queued_box(prompt[:50], image_size, count_label, pending),
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        asyncio.create_task(process_queue())
        return

    # ── Other menu items ──

    if data == "gen":
        ud["awaiting_prompt"] = True
        await safe_edit(query.message,
            box("🎨 Generate Image",
                "━━ 🎨 *Ready to Create!* ━━\n\n"
                "   • 📝 Send me any text description\n"
                "   • 🖼️ I'll generate an image using AI\n"
                "   • 📁 Or upload a `.txt` file\n\n"
                "━━ 💡 *Example Prompts* ━━\n"
                "   • `a cat wearing a hat`\n"
                "   • `futuristic city at night`\n"
                "   • `a beautiful mountain landscape`\n\n"
                "━━ ⏰ *Go Ahead* ━━\n"
                "   Type your prompt now!",
                emoji="🎨"),
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        return

    if data == "myqueue":
        items = Queue.get_user_queue(user_id)
        if not items:
            await safe_edit(query.message,
                box("📋 Your Queue",
                    "━━ 📋 *Queue Status* ━━\n\n"
                    "   • ✅ Your queue is empty!\n"
                    "   • 🎨 Send a prompt to get started\n"
                    "   • ⚡ No pending tasks right now",
                    emoji="📋"),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            return
        icon = {"pending": "⏳", "processing": "🔄", "done": "✅", "fail": "❌"}
        lines = [
            SEP,
            center("📋 Your Queue"),
            SEP,
            f"  • 📊 *Total:* {len(items)} item(s)",
            "",
        ]
        for item in items[-15:]:
            si = icon.get(item["status"], "❓")
            p = item["prompt"][:30]
            batch = f" ({item.get('batch_index',0)+1}/{item.get('batch_total',1)})" if item.get('batch_total',1) > 1 else ""
            lines.append(f"  • {si} `{p}`{batch}")
        lines += [
            "",
            SEP,
            "📌 *Status Guide*",
            "  ⏳ Pending    🔄 Processing",
            "  ✅ Done       ❌ Failed",
            END,
            "_🤖 Powered by @TurabCoder_",
        ]
        await safe_edit(query.message,"\n".join(lines), parse_mode="Markdown", reply_markup=main_menu())
        return

    if data == "status":
        qs = Queue.stats()
        ac = Account.count()
        ses = get_session_status()
        text = status_box(ac, qs['pending'], qs.get('processing',0), qs['done'], qs['fail'], ses)
        kb = [[InlineKeyboardButton("🔄 Refresh Status", callback_data="status"),
               InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")]]
        await safe_edit(query.message,text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "accounts":
        docs = Account.get_all()
        if not docs:
            await safe_edit(query.message,
                accounts_box([]),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            return
        now = datetime.now(timezone.utc)
        lines = []
        for i, d in enumerate(docs[:10]):
            c = len(d.get("cookies", []))
            name = d.get("profile_name") or d.get("label", f"#{i+1}")
            exp = "❌" if d.get("expired") else ("⏳" if d.get("limited") else "✅")
            src = "🌐" if d.get("source") == "extension" else "📦"
            first_loaded = d.get("first_loaded_at")
            if first_loaded and first_loaded.tzinfo is None:
                first_loaded = first_loaded.replace(tzinfo=timezone.utc)
            is_fresh = first_loaded and (now - first_loaded).total_seconds() < 3600
            fresh_tag = "🆕" if is_fresh else ""
            lines.append(f"   • {src}{exp}{fresh_tag} `{name}` ({c} cookies)")
        if len(docs) > 10:
            lines.append(f"\n   • ...and {len(docs)-10} more")
        await safe_edit(query.message,accounts_box(lines), parse_mode="Markdown", reply_markup=main_menu())
        return

    if data == "help":
        await safe_edit(query.message,help_box(), parse_mode="Markdown", reply_markup=main_menu())
        return

    # ── Admin ──

    if data == "admin" and is_adm:
        text = (
            f"{SEP}\n"
            f"{center('⚙️ Admin Control Panel')}\n"
            f"{SEP}\n\n"
            f"📋 *Available Actions*\n"
            f"  • ➕ Add Account — Paste cookies JSON\n"
            f"  • 📦 Export — Download all accounts\n"
            f"  • 📥 Import — Upload accounts JSON\n"
            f"  • 🔄 Check Sessions — Validate all\n"
            f"  • ⏰ Reset Limits — Restore limited accts\n\n"
            f"⚙️ *Auto-Systems*\n"
            f"  • 🔄 Session check: Every 5 minutes\n"
            f"  • ⏰ Limit reset: Every 5 minutes\n"
            f"  • 📬 Notifications sent here\n\n"
            f"{END}"
        )
        await safe_edit(query.message,text, parse_mode="Markdown", reply_markup=admin_menu())
        return

    if data == "export" and is_adm:
        data_list = export_accounts()
        if not data_list:
            await safe_edit(query.message,
                box("📦 Export",
                    "━━ 📭 *Nothing to Export* ━━\n\n"
                    "   • 📦 No accounts found in database\n"
                    "   • ➕ Add accounts first via Admin\n"
                    "   • 🌐 Or sync via Chrome extension",
                    emoji="📦"),
                parse_mode="Markdown",
                reply_markup=admin_menu()
            )
            return
        bio = io.BytesIO(jmod.dumps(data_list, indent=2, default=str).encode())
        bio.name = "gpt-accounts.json"
        await query.message.reply_document(bio, caption="📦 GPT Accounts Export — @TurabCoder")
        await safe_edit(query.message,
            box("📦 Export Complete",
                "━━ ✅ *Export Successful* ━━\n\n"
                f"   • 📄 File: `gpt-accounts.json`\n"
                f"   • 👤 Accounts: {len(data_list)}\n"
                f"   • 🔐 Data: Cookies (Keep Private!)\n\n"
                "━━ ⚠️ *Security Warning* ━━\n"
                "   • 🔒 Keep this file secure!\n"
                "   • 🚫 Never share with anyone\n"
                "   • 🗑️ Delete after use if possible",
                emoji="📦"),
            parse_mode="Markdown",
            reply_markup=admin_menu()
        )
        return

    if data == "import_prompt" and is_adm:
        context.user_data["awaiting_import"] = True
        await safe_edit(query.message,
            box("📥 Import",
                "━━ 📥 *Import Accounts* ━━\n\n"
                "   • 📁 Send a `.json` file to import\n"
                "   • 📋 Format: Export format only\n"
                "   • 🔄 Duplicates auto-renamed\n\n"
                "━━ ⚠️ *Important* ━━\n"
                "   • Existing labels get `-N` suffix\n"
                "   • Invalid entries are skipped\n"
                "   • Send the file now!",
                emoji="📥"),
            parse_mode="Markdown",
            reply_markup=admin_menu()
        )
        return

    if data == "add_account" and is_adm:
        context.user_data["awaiting_account_json"] = True
        text = (
            f"{SEP}\n"
            f"{center('➕ Add New Account')}\n"
            f"{SEP}\n\n"
            f"📋 *Instructions*\n\n"
            f"  • 📋 Paste cookies JSON from Chrome extension\n"
            f"  • 📝 Format:\n"
            f"     `[{{\"name\":\"...\",\"value\":\"...\",...}}]`\n\n"
            f"🔖 *Custom Label (Optional)*\n\n"
            f"  • `MyName | [{{\"name\"...}}]`\n\n"
            f"⚠️ *Important*\n"
            f"  • 🔐 Keep cookies private\n"
            f"  • 🔄 Same label = auto-update\n"
            f"  • ❌ Invalid JSON will be rejected\n"
            f"{END}"
        )
        await safe_edit(query.message,text, parse_mode="Markdown", reply_markup=admin_menu())
        return

    if data == "check_sessions" and is_adm:
        await safe_edit(query.message,
            box("🔄 Sessions",
                "━━ 🔄 *Checking All Sessions* ━━\n\n"
                "   • 🔍 Validating account cookies...\n"
                "   • ⏰ Checking limit timers...\n"
                "   • ⏳ Please wait, this may take a moment",
                emoji="🔄"),
            parse_mode="Markdown"
        )
        await check_session()
        n = reset_limited_accounts()
        ses = get_session_status()
        lines = [
            SEP,
            center("✅ Session Check Complete"),
            SEP,
            f"  • 🔄 Limits Reset: `{n}` account(s)",
            "",
            SEP,
            "📋 *Account Status Report*",
        ]
        for s in ses:
            lines.append(f"  • {s}")
        lines += [
            "",
            SEP,
            "📌 *Legend*",
            "  ✅ Active    ❌ Expired",
            "  ⏳ Limited   ⚠️ Errors",
            END,
            "_🤖 Powered by @TurabCoder_",
        ]
        await safe_edit(query.message,
            "\n".join(lines), parse_mode="Markdown", reply_markup=admin_menu()
        )
        return

    if data == "reset_limits" and is_adm:
        n = reset_limited_accounts()
        ses = get_session_status()
        lines = [
            SEP,
            center("⏰ Limit Reset Complete"),
            SEP,
            f"  • 🔄 Restored: `{n}` account(s)",
            "",
            SEP,
            "📋 *Current Status*",
        ]
        for s in ses:
            lines.append(f"  • {s}")
        lines += [
            SEP,
            "📌 *Legend*",
            "  ✅ Active    ❌ Expired",
            "  ⏳ Limited   ⚠️ Errors",
            END,
            "_🤖 Powered by @TurabCoder_",
        ]
        await safe_edit(query.message,"\n".join(lines), parse_mode="Markdown", reply_markup=admin_menu())
        return

    if data == "back_main":
        await safe_edit(query.message,menu_header(), parse_mode="Markdown", reply_markup=main_menu(user_id))
        return

# ── Queue Processor ──

async def process_queue():
    async with queue_semaphore:
        while True:
            item = Queue.get_pending()
            if not item:
                break

            qid = item["_id"]
            user_id = item["user_id"]
            image_size = item.get("image_size", "1:1")

            Queue.update_status(qid, Queue.STATUS_PROCESSING)

            is_bulk = item.get("is_bulk")
            if is_bulk:
                prompts = item.get("prompts", [])
                progress_msg = None
                try:
                    from telegram import Bot
                    bot = Bot(config.BOT_TOKEN)
                    msg = (
                        f"{SEP}\n"
                        f"{center('📁 Bulk Processing')}\n"
                        f"{SEP}\n\n"
                        f"  • 📄 Total: `{len(prompts)}` prompts\n"
                        f"  • 📐 Size: `{image_size}`\n\n"
                        f"⏳ Processing..."
                    )
                    progress_msg = await bot.send_message(
                        chat_id=user_id, text=msg, parse_mode="Markdown"
                    )
                except Exception:
                    pass

                async def bulk_cb(msg: str):
                    if progress_msg:
                        try:
                            await progress_msg.edit_text(
                                f"{SEP}\n{center('📁 Bulk Processing')}\n{SEP}\n\n"
                                f"  • 📄 Total: `{len(prompts)}` prompts\n"
                                f"  • 📐 Size: `{image_size}`\n\n"
                                f"  {msg}",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass

                from worker import submit_bulk
                results = await submit_bulk(prompts, image_size=image_size, progress_callback=bulk_cb)
                processed = len(results)
                success_count = sum(1 for r in results if r.get("success"))
                fail_count = sum(1 for r in results if not r.get("success"))
                Queue.update_status(qid, Queue.STATUS_DONE if fail_count == 0 else Queue.STATUS_FAIL)

                summary = (
                    f"{SEP}\n{center('✅ Bulk Complete')}\n{SEP}\n\n"
                    f"  • ✅ Success: `{success_count}`\n"
                    f"  • ❌ Failed: `{fail_count}`\n"
                    f"  • 📐 Size: `{image_size}`"
                )

                # Remaining prompts due to limit hit
                remaining_prompts = prompts[processed:] if processed < len(prompts) else []
                if remaining_prompts:
                    remaining_file = io.BytesIO("\n\n".join(remaining_prompts).encode())
                    remaining_file.name = f"remaining-{len(remaining_prompts)}-prompts.txt"
                    try:
                        from telegram import Bot
                        bot = Bot(config.BOT_TOKEN)
                        await bot.send_document(
                            chat_id=user_id,
                            document=remaining_file,
                            caption=(
                                f"{SEP}\n{center('📄 Remaining Prompts')}\n{SEP}\n\n"
                                f"⏳ Limit reached after `{processed}/{len(prompts)}`\n\n"
                                f"📁 Re-share this file to continue from where you left off."
                            ),
                            parse_mode="Markdown",
                        )
                    except Exception:
                        pass
                    summary += f"\n  • 📁 Remaining: `{len(remaining_prompts)}` prompts saved to file"

                if progress_msg:
                    try:
                        await progress_msg.edit_text(summary, parse_mode="Markdown")
                    except Exception:
                        pass

                for i, r in enumerate(results):
                    if r.get("success") and r.get("image_url"):
                        await send_image_to_user({
                            "user_id": user_id,
                            "prompt": prompts[i],
                            "batch_index": i,
                            "batch_total": len(prompts),
                        }, r["image_url"])
                continue

            prompt = item["prompt"]
            batch_idx = item.get("batch_index", 0)
            batch_total = item.get("batch_total", 1)

            progress_msg = None
            try:
                from telegram import Bot
                bot = Bot(config.BOT_TOKEN)
                batch_info = f" ({batch_idx+1}/{batch_total})" if batch_total > 1 else ""
                msg = queue_box(prompt, image_size, batch_info)
                msg += "\n\n⏳ Starting..."
                progress_msg = await bot.send_message(
                    chat_id=user_id, text=msg, parse_mode="Markdown"
                )
            except Exception:
                pass

            async def progress_callback(msg: str):
                nonlocal progress_msg
                if progress_msg:
                    try:
                        batch_info = f" ({batch_idx+1}/{batch_total})" if batch_total > 1 else ""
                        text = progress_box(prompt, msg, batch_info)
                        await progress_msg.edit_text(text, parse_mode="Markdown")
                    except Exception:
                        pass

            result = await submit_prompt(
                prompt, image_size=image_size, progress_callback=progress_callback
            )

            if result.get("success") and result.get("image_url"):
                Queue.update_status(qid, Queue.STATUS_DONE, image_url=result["image_url"])
                await send_image_to_user(item, result["image_url"], progress_msg)
            else:
                err = result.get("error", "Unknown error")[:100]
                Queue.update_status(qid, Queue.STATUS_FAIL, error=err)
                if progress_msg:
                    try:
                        await progress_msg.edit_text(
                            error_box("😵‍💫 Generation Failed",
                                      f"`{prompt[:40]}`\n\n{err}",
                                      tips=["🔄 Try again in a few minutes",
                                            "✅ Check account status in admin",
                                            "📬 Contact @TurabCoder for help"]),
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
            await asyncio.sleep(2)

async def send_image_to_user(item, image_url, progress_msg=None):
    import aiohttp
    from telegram import Bot
    bot = Bot(config.BOT_TOKEN)
    user_id = item["user_id"]
    prompt = item["prompt"]
    batch_idx = item.get("batch_index", 0)
    batch_total = item.get("batch_total", 1)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    bio = io.BytesIO(data)
                    from utils.helpers import make_image_filename
                    bio.name = make_image_filename(prompt)
                    batch_tag = f" ({batch_idx+1}/{batch_total})" if batch_total > 1 else ""
                    caption = image_caption(prompt, batch_tag)

                    await bot.send_photo(
                        chat_id=user_id, photo=bio, caption=caption, parse_mode="Markdown"
                    )
                    if progress_msg:
                        try:
                            await progress_msg.delete()
                        except Exception:
                            pass
                    return
    except Exception as e:
        print(f"[bot] Send image error: {e}")

    if progress_msg:
        try:
            await progress_msg.edit_text(result_box(prompt, image_url), parse_mode="Markdown")
        except Exception:
            pass
    else:
        try:
            await bot.send_message(
                chat_id=user_id, text=result_box(prompt, image_url), parse_mode="Markdown"
            )
        except Exception:
            pass

async def status_command(update, context):
    qs = Queue.stats()
    ac = Account.count()
    ses = get_session_status()
    await update.message.reply_text(
        status_box(ac, qs['pending'], qs.get('processing',0), qs['done'], qs['fail'], ses),
        parse_mode="Markdown",
        reply_markup=main_menu(update.effective_user.id)
    )
