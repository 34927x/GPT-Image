import asyncio, io, json as jmod, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters, ContextTypes)

import config
from db import init_db
from models import Account, Queue
from accounts.manager import (is_admin, export_accounts, import_accounts,
                              get_session_status, mark_expired, add_manual_account,
                              reset_limited_accounts, parse_limit_reset_time)
from worker import submit_prompt, close as close_worker, check_session
from ui import (box, error_box, menu_header, queue_box, progress_box,
                result_box, status_box, accounts_box, queued_box, help_box,
                image_caption, SEP, DIV, END)

queue_semaphore = asyncio.Semaphore(1)

# ── Keyboards ──

def main_menu():
    kb = [
        [InlineKeyboardButton("🎨 Generate", callback_data="gen")],
        [InlineKeyboardButton("📋 Queue", callback_data="myqueue"),
         InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("👥 Accounts", callback_data="accounts"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    return InlineKeyboardMarkup(kb)

def admin_menu():
    kb = [
        [InlineKeyboardButton("➕ Add", callback_data="add_account")],
        [InlineKeyboardButton("📦 Export", callback_data="export"),
         InlineKeyboardButton("📥 Import", callback_data="import_prompt")],
        [InlineKeyboardButton("🔄 Check", callback_data="check_sessions"),
         InlineKeyboardButton("⏰ Reset", callback_data="reset_limits")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(kb)

def size_menu():
    kb = [
        [InlineKeyboardButton("⬜ 1:1", callback_data="size_1:1"),
         InlineKeyboardButton("🖥️ 16:9", callback_data="size_16:9")],
        [InlineKeyboardButton("📱 9:16", callback_data="size_9:16"),
         InlineKeyboardButton("📺 4:3", callback_data="size_4:3")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(kb)

def bulk_menu(prompt, image_size):
    # Prompt stored in user_data, only send size+count in callback (64-byte Telegram limit)
    kb = [
        [InlineKeyboardButton("1️⃣ Single Image", callback_data=f"b_{image_size}_1"),
         InlineKeyboardButton("2️⃣ Double Pack", callback_data=f"b_{image_size}_2")],
        [InlineKeyboardButton("4️⃣ Quad Pack", callback_data=f"b_{image_size}_4")],
        [InlineKeyboardButton("🔙 Back", callback_data="gen")],
    ]
    return InlineKeyboardMarkup(kb)

# ── Handlers ──

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "━━━━━━━━━━━━━━━━━━━\n"
        "🤖 *🎨 Welcome to GPT Image Bot!* 🎨\n"
        "─────────────────────\n\n"
        "━━ 🚀 *How It Works* ━━\n"
        "   • 📝 Send any text → AI generates image\n"
        "   • 📁 Upload `.txt` file → Bulk processing\n"
        "   • 🖼️ Images delivered right in this chat\n"
        "   • 🔄 Multi-account auto-failover\n\n"
        "━━ 📋 *Quick Start* ━━\n"
        "   • ✏️ Just type what you want to see\n"
        "   • 📐 Choose aspect ratio when prompted\n"
        "   • 🔢 Select count (1 / 2 / 4 images)\n"
        "   • ✅ Done! Image will appear here\n\n"
        "━━ 💡 *Tips* ━━\n"
        "   • 🎨 Be descriptive for best results\n"
        "   • 📄 Separate prompts by blank line in `.txt`\n"
        "   • 📊 Use /menu for full options\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "─────────────────────"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(menu_header(), parse_mode="Markdown", reply_markup=main_menu())

# ── Auto-detect: any text = prompt ──

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    ud = context.user_data

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

    ud["pending_prompt"] = txt
    ud["awaiting_size"] = True
    await update.message.reply_text(
        box("📐 Choose Size",
            f"━━ 📐 *Select Aspect Ratio* ━━\n\n"
            f"   • ✏️ Prompt: `{txt[:100]}`\n\n"
            "   Choose image shape below:",
            emoji="📐"),
        parse_mode="Markdown",
        reply_markup=size_menu()
    )

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
    context.user_data["pending_prompt"] = prompt
    context.user_data["awaiting_size"] = True
    await update.message.reply_text(
        box("📐 Choose Size",
            f"━━ 📐 *Select Aspect Ratio* ━━\n\n"
            f"   • ✏️ Prompt: `{prompt[:100]}`\n\n"
            "   Choose image shape below:",
            emoji="📐"),
        parse_mode="Markdown",
        reply_markup=size_menu()
    )

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
            count = 0
            for p in prompts:
                Queue.add(p, user_id, image_size=image_size, bulk_count=1)
                count += 1
            ud.pop("pending_size", None)
            await query.edit_message_text(
                box("✅ Bulk Queued",
                    "━━ ✅ *Bulk Upload Successful* ━━\n\n"
                    f"   • 📥 Added `{count}` prompts from file\n"
                    f"   • 📐 Size: `{image_size}`\n"
                    f"   • 🎯 Position: `#{Queue.get_pending_count()}`\n\n"
                    "━━ ⏰ *What Now?* ━━\n"
                    "   • 🔄 Processing automatically in background\n"
                    "   • 📬 Each image sent here when ready\n"
                    "   • 📊 Check status anytime",
                    emoji="✅"),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            asyncio.create_task(process_queue())
            return

        if not prompt:
            await query.edit_message_text(
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
        await query.edit_message_text(
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
            await query.edit_message_text(
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
            await query.edit_message_text(
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
        await query.edit_message_text(
            queued_box(prompt[:50], image_size, count_label, pending),
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        asyncio.create_task(process_queue())
        return

    # ── Other menu items ──

    if data == "gen":
        ud["awaiting_prompt"] = True
        await query.edit_message_text(
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
            await query.edit_message_text(
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
            "📋 *Your Queue*",
            DIV,
            f"   • 📊 *Total:* {len(items)} item(s)",
            "",
        ]
        for item in items[-15:]:
            si = icon.get(item["status"], "❓")
            p = item["prompt"][:30]
            batch = f" ({item.get('batch_index',0)+1}/{item.get('batch_total',1)})" if item.get('batch_total',1) > 1 else ""
            lines.append(f"   • {si} `{p}`{batch}")
        lines += [
            "",
            SEP,
            "━━ 📌 *Status Guide* ━━",
            "   ⏳ Pending    🔄 Processing",
            "   ✅ Done       ❌ Failed",
            END,
            "_🤖 Powered by @TurabCoder_",
        ]
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=main_menu())
        return

    if data == "status":
        qs = Queue.stats()
        ac = Account.count()
        ses = get_session_status()
        text = status_box(ac, qs['pending'], qs.get('processing',0), qs['done'], qs['fail'], ses)
        kb = [[InlineKeyboardButton("🔄 Refresh Status", callback_data="status"),
               InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "accounts":
        docs = Account.get_all()
        if not docs:
            await query.edit_message_text(
                accounts_box([]),
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            return
        lines = []
        for i, d in enumerate(docs[:10]):
            c = len(d.get("cookies", []))
            name = d.get("profile_name") or d.get("label", f"#{i+1}")
            exp = "❌" if d.get("expired") else ("⏳" if d.get("limited") else "✅")
            src = "🌐" if d.get("source") == "extension" else "📦"
            lines.append(f"   • {src}{exp} `{name}` ({c} cookies)")
        if len(docs) > 10:
            lines.append(f"\n   • ...and {len(docs)-10} more")
        await query.edit_message_text(accounts_box(lines), parse_mode="Markdown", reply_markup=main_menu())
        return

    if data == "help":
        await query.edit_message_text(help_box(), parse_mode="Markdown", reply_markup=main_menu())
        return

    # ── Admin ──

    if data == "admin" and is_adm:
        text = (
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚙️ *Admin Control Panel* ⚙️\n"
            "─────────────────────\n\n"
            "━━ 📋 *Available Actions* ━━\n"
            "   • ➕ Add Account — Paste cookies JSON\n"
            "   • 📦 Export — Download all accounts\n"
            "   • 📥 Import — Upload accounts JSON\n"
            "   • 🔄 Check Sessions — Validate all\n"
            "   • ⏰ Reset Limits — Restore limited accts\n\n"
            "━━ ⚙️ *Auto-Systems* ━━\n"
            "   • 🔄 Session check: Every 30 minutes\n"
            "   • ⏰ Limit reset: Every 5 minutes\n"
            "   • 📬 Notifications sent here\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "─────────────────────"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_menu())
        return

    if data == "export" and is_adm:
        data_list = export_accounts()
        if not data_list:
            await query.edit_message_text(
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
        await query.edit_message_text(
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
        await query.edit_message_text(
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
            "━━━━━━━━━━━━━━━━━━━\n"
            "➕ *Add New Account* ➕\n"
            "─────────────────────\n\n"
            "━━ 📋 *Instructions* ━━\n\n"
            "   • 📋 Paste cookies JSON from Chrome extension\n"
            "   • 📝 Format:\n"
            "      `[{\"name\":\"...\",\"value\":\"...\",...}]`\n\n"
            "━━ 🔖 *Custom Label (Optional)* ━━\n\n"
            "   • `MyName | [{\"name\"...}]`\n\n"
            "━━ ⚠️ *Important* ━━\n"
            "   • 🔐 Keep cookies private\n"
            "   • 🔄 Same label = auto-update\n"
            "   • ❌ Invalid JSON will be rejected\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "─────────────────────"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_menu())
        return

    if data == "check_sessions" and is_adm:
        await query.edit_message_text(
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
            "✅ *Session Check Complete* ✅",
            DIV,
            f"   • 🔄 Limits Reset: `{n}` account(s)",
            "",
            "━━ 📋 *Account Status Report* ━━",
        ]
        for s in ses:
            lines.append(f"   • {s}")
        lines += [
            "",
            SEP,
            "━━ 📌 *Status Legend* ━━",
            "   ✅ Active    ❌ Expired",
            "   ⏳ Limited   ⚠️ Errors",
            END,
            "_🤖 Powered by @TurabCoder_",
        ]
        await query.edit_message_text(
            "\n".join(lines), parse_mode="Markdown", reply_markup=admin_menu()
        )
        return

    if data == "reset_limits" and is_adm:
        n = reset_limited_accounts()
        ses = get_session_status()
        lines = [
            SEP,
            "⏰ *Limit Reset Complete* 🔄",
            DIV,
            f"   • 🔄 Restored: `{n}` account(s)",
            "",
            "━━ 📋 *Current Status* ━━",
        ]
        for s in ses:
            lines.append(f"   • {s}")
        lines += [
            SEP,
            "━━ 📌 *Legend* ━━",
            "   ✅ Active    ❌ Expired",
            "   ⏳ Limited   ⚠️ Errors",
            END,
            "_🤖 Powered by @TurabCoder_",
        ]
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=admin_menu())
        return

    if data == "back_main":
        await query.edit_message_text(menu_header(), parse_mode="Markdown", reply_markup=main_menu())
        return

# ── Queue Processor ──

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
        reply_markup=main_menu()
    )
