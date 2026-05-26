import asyncio, os, sys, json, hmac, hashlib, io, re
import json as jmod
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters, ContextTypes)

import aiohttp as _aiohttp
import config
from config import init_db, queue_col, accounts_col, Queue, Account
from utils.worker_utils import (is_admin, export_accounts, import_accounts,
                   get_session_status, mark_expired,
                   reset_limited_accounts, parse_limit_reset_time)


# --- BOT HANDLERS & UI ---
# --- UI HELPERS ---
SEP = "──────────────────────────────"
END = SEP

def center(text):
    mid = len(SEP)
    t = str(text)
    pad = max(0, mid - len(t))
    left = pad // 2
    right = pad - left
    return " " * left + t + " " * right

def box(title, body, emoji="🤖", credit=True):
    lines = [
        f"{emoji} **{title.upper()}**",
        SEP,
        body,
        END,
    ]
    if credit:
        lines += ["", "🤖 *DALL·E Rotator* | @TurabCoder 🚀"]
    return "\n".join(lines)

def error_box(title="🚨 System Alert", body="An unexpected error occurred.", reasons=None, tips=None):
    if reasons is None:
        reasons = [
            "🌐 Server is busy or experiencing high traffic",
            "🔌 Temporary network connectivity issue",
            "🔑 Account session has expired",
        ]
    if tips is None:
        tips = [
            "🔄 Wait a moment and try again",
            "✅ Verify your accounts are still active",
            "📬 Contact support if the issue persists",
        ]
    lines = [
        "⚠️ **SYSTEM DIAGNOSTIC ALERT** ⚠️",
        SEP,
        f"🔴 **Error Details:** `{body}`",
        SEP,
        "🔍 *Potential Causes:*",
    ]
    for r in reasons:
        lines.append(f"  {r}")
    lines += [
        "",
        "💡 *Recommended Actions:*",
    ]
    for t in tips:
        lines.append(f"  {t}")
    lines += [
        SEP,
        "🆘 *Support:* @TurabCoder 🛠️"
    ]
    return "\n".join(lines)

def menu_header(title="🧭 Main Menu"):
    lines = [
        f"{title.upper()}",
        SEP,
        "👇 Use the buttons below to control the bot:",
        END,
    ]
    return "\n".join(lines)

def queue_box(prompt, image_size, batch_info=""):
    lines = [
        "🎨 **IMAGE GENERATION STARTED** 🚀",
        SEP,
        f"📝 **Prompt:** `{prompt[:100]}`{batch_info}",
        f"📐 **Aspect Ratio:** `{image_size}`",
        SEP,
        "⏳ **Status:** Queued & Processing...",
        "⚡ **ETA:** Usually 30–90 seconds ⏰",
        END,
        "🤖 *DALL·E Rotator* | @TurabCoder ✨",
    ]
    return "\n".join(lines)

def progress_box(prompt, step, batch_info=""):
    lines = [
        "⏳ **GENERATION IN PROGRESS** ⚙️",
        SEP,
        f"📝 **Prompt:** `{prompt[:50]}...`{batch_info}",
        "",
        "📌 **Current Step:**",
        f"   └─ {step}",
        SEP,
        "☕ Please wait while we process your request...",
        END,
        "🤖 *DALL·E Rotator* | @TurabCoder ✨",
    ]
    return "\n".join(lines)

def result_box(prompt, image_url, batch_info=""):
    lines = [
        "🎉 **GENERATION COMPLETE** ✅",
        SEP,
        f"📝 **Prompt:** `{prompt[:120]}`{batch_info}",
        SEP,
        "🔗 **Direct Download Link:**",
        f"   └─ [📥 Click Here to Download]({image_url})",
        "",
        "📤 The image has also been sent above!",
        END,
        "🤖 *DALL·E Rotator* | @TurabCoder 🚀",
    ]
    return "\n".join(lines)

def status_box(accounts, pending, processing, done, failed, sessions):
    lines = [
        "📊 **SYSTEM STATUS REPORT** 📊",
        SEP,
        "📋 **Queue Overview:**",
        f"  • 👤 Active Accounts: `{accounts}`",
        f"  • ⏳ Tasks Pending: `{pending}`",
        f"  • 🔄 Processing: `{processing}`",
        f"  • ✅ Completed: `{done}`",
        f"  • ❌ Failed: `{failed}`",
        SEP,
        "🔐 **Recent Active Sessions:**",
    ]
    for s in sessions[:5]:
        lines.append(f"  • {s}")
    if len(sessions) > 5:
        lines.append(f"  • ... and {len(sessions)-5} more")
    lines += [
        "",
        SEP,
        "⚙️ **System Configuration:**",
        "  • 🔍 Session Check: Lazy/On-Demand",
        "  • ⏰ Limit Auto-Reset: Every 5m",
        "  • 🔄 Max Retry Count: 5 attempts",
        "  • 🛡️ Memory Optimization: Active (400MB limit)",
        SEP,
        "🟢 **Status:** All Systems Online & Healthy",
        END,
        "🤖 *DALL·E Rotator* | @TurabCoder 🚀",
    ]
    return "\n".join(lines)

def accounts_box(entries):
    lines = [
        "👥 **REGISTERED ACCOUNTS** 👥",
        SEP,
    ]
    if not entries:
        lines += [
            "📭 **No Accounts Connected**",
            "",
            "💡 **How to Add Accounts:**",
            "  1. 🌐 Install the Chrome extension",
            "  2. 🔑 Log in to chatgpt.com",
            "  3. 🔌 Click extension icon to auto-sync",
            "  4. 📦 Or add cookies manually via Admin Panel",
            END,
            "🤖 *DALL·E Rotator* | @TurabCoder 🚀",
        ]
        return "\n".join(lines)
    for e in entries:
        lines.append(f"  {e}")
    lines += [
        "",
        SEP,
        "📌 **Legend:**",
        "  🌐 = Chrome Sync  📦 = Manual Import",
        "  ✅ = Session OK   ❌ = Expired Session",
        "  ⏳ = Rate Limited ⚠️ = Login Error",
        END,
        "🤖 *DALL·E Rotator* | @TurabCoder 🚀",
    ]
    return "\n".join(lines)

def queued_box(prompt, size, count, position):
    lines = [
        "📥 **TASK QUEUED SUCCESSFULLY** ✅",
        SEP,
        "📋 **Task Specifications:**",
        f"  • ✏️ Prompt: `{prompt[:100]}`",
        f"  • 📐 Size/Aspect Ratio: `{size}`",
        f"  • 🔢 Type: `{count}`",
        f"  • 🎯 Position in Queue: `#{position}`",
        SEP,
        "🔄 **Next Steps:**",
        "  • ⚙️ Your task will process automatically in the background.",
        "  • 📬 Generated images will be delivered directly here.",
        "",
        "💡 *Tip:* Use `/status` to view queue depth.",
        END,
        "🤖 *DALL·E Rotator* | @TurabCoder ✨",
    ]
    return "\n".join(lines)

def help_box():
    lines = [
        "📖 **DALL·E ROTATOR USER GUIDE** 📖",
        SEP,
        "🚀 **Quick Start:**",
        "  • ✏️ **Single Image:** Send your text prompt directly.",
        "  • 📁 **Bulk Gen:** Upload a `.txt` file with prompts (one per line).",
        "  • 📬 All images will be delivered directly to this chat.",
        SEP,
        "⌨️ **Available Commands:**",
        "  • `/menu` 🧭 — Access navigation & control dashboard",
        "  • `/gen <prompt>` 🎨 — Quick generation command",
        "  • `/status` 📊 — View queue depth & system diagnostics",
        "  • `/start` 🚀 — Initialize/restart the bot session",
        SEP,
        "💡 **Pro Tips:**",
        "  • 📝 Separate prompts by a blank line in text files.",
        "  • 👥 Connect multiple accounts to enable automatic rotation.",
        "  • 🎨 Use descriptive prompts for high-quality DALL·E output.",
        SEP,
        "🔧 **Troubleshooting:**",
        "  • ❌ Session Expired -> Re-sync cookies via Chrome extension.",
        "  • ⏳ Rate Limited -> Wait for automatic reset or switch accounts.",
        "  • 📬 Support Queries -> Contact @TurabCoder",
        END,
        "🤖 *DALL·E Rotator* | @TurabCoder 🚀",
    ]
    return "\n".join(lines)

def image_caption(prompt, batch_info=""):
    lines = [
        "✨ **GENERATED IMAGE** 🎨",
        SEP,
        f"📝 `{prompt[:200]}`{batch_info}",
        SEP,
        "📥 Delivered & Saved ✅",
        END,
        "🤖 *DALL·E Rotator* | @TurabCoder 🚀",
    ]
    return "\n".join(lines)


# --- BOT HANDLERS ---

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
        from worker.entry import process_account_entry
        ok, msg = process_account_entry(cookies_str, source="manual", label=label)
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
                "   • 🔍 Checking account status...\\n"
                "   • ⏰ Checking limit timers...\\n"
                "   • ⏳ Please wait...",
                emoji="🔄"),
            parse_mode="Markdown"
        )
        # No Playwright on Heroku — just reset limits and show DB status
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

# ── Remote Worker HTTP Helpers ──

async def call_remote_worker(endpoint, payload, timeout=300):
    """Call the local Chromium worker via HTTP."""
    url = f"{config.WORKER_URL}{endpoint}"
    headers = {"X-Worker-Secret": config.WORKER_SECRET, "Content-Type": "application/json"}
    try:
        async with _aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=_aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    return {"success": False, "error": f"Worker HTTP {resp.status}: {text[:100]}"}
    except _aiohttp.ClientError as e:
        return {"success": False, "error": f"Worker unreachable: {str(e)[:80]}"}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Worker timeout (image generation took too long)"}

async def check_worker_health():
    """Check if the local worker is alive."""
    url = f"{config.WORKER_URL}/health"
    headers = {"X-Worker-Secret": config.WORKER_SECRET}
    try:
        async with _aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers,
                                   timeout=_aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return None

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
                        f"⏳ Sending to worker..."
                    )
                    progress_msg = await bot.send_message(
                        chat_id=user_id, text=msg, parse_mode="Markdown"
                    )
                except Exception:
                    pass

                # Call remote worker for bulk
                resp = await call_remote_worker("/process-bulk", {
                    "prompts": prompts, "image_size": image_size
                }, timeout=len(prompts) * 180)

                results = resp.get("results", [])
                if not results and resp.get("error"):
                    results = [{"success": False, "error": resp["error"]} for _ in prompts]

                success_count = sum(1 for r in results if r.get("success"))
                fail_count = sum(1 for r in results if not r.get("success"))
                Queue.update_status(qid, Queue.STATUS_DONE if fail_count == 0 else Queue.STATUS_FAIL)

                summary = (
                    f"{SEP}\n{center('✅ Bulk Complete')}\n{SEP}\n\n"
                    f"  • ✅ Success: `{success_count}`\n"
                    f"  • ❌ Failed: `{fail_count}`\n"
                    f"  • 📐 Size: `{image_size}`"
                )

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
                msg += "\n\n⏳ Sending to worker..."
                progress_msg = await bot.send_message(
                    chat_id=user_id, text=msg, parse_mode="Markdown"
                )
            except Exception:
                pass

            # Update progress
            if progress_msg:
                try:
                    batch_info = f" ({batch_idx+1}/{batch_total})" if batch_total > 1 else ""
                    text = progress_box(prompt, "🔄 Processing on local worker...", batch_info)
                    await progress_msg.edit_text(text, parse_mode="Markdown")
                except Exception:
                    pass

            # Call remote worker
            result = await call_remote_worker("/process", {
                "prompt": prompt, "image_size": image_size
            })

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



# --- FASTAPI & LIFESPAN ---

telegram_app = None
API_KEY = os.getenv("API_KEY", "")
SESSION_CHECK_INTERVAL = int(os.getenv("SESSION_CHECK_INTERVAL", "5"))
LIMIT_RESET_INTERVAL = int(os.getenv("LIMIT_RESET_INTERVAL", "5"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_app
    await init_db()

    telegram_app = Application.builder().token(config.BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("menu", menu_command))
    telegram_app.add_handler(CommandHandler("gen", gen_command))
    telegram_app.add_handler(CommandHandler("status", status_command))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    telegram_app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.delete_webhook(drop_pending_updates=True)
    await telegram_app.updater.start_polling()

    acct_count = Account.count()
    queue_count = Queue.get_pending_count()
    print(f"[main] Bot started — {acct_count} accounts, {queue_count} queued items")

    session_task = asyncio.create_task(session_check_loop())
    limit_task = asyncio.create_task(limit_reset_loop())

    # Check if local worker is reachable
    health = await check_worker_health()
    if health:
        print(f"[main] Local worker connected ✅ — {health.get('accounts_available', '?')} accounts available")
    else:
        print(f"[main] ⚠️ Local worker not reachable at {config.WORKER_URL} — images will fail until worker is started")

    # Process any pending queue items from before restart
    if queue_count > 0:
        print(f"[main] Processing {queue_count} pending queue items...")
        asyncio.create_task(process_queue())

    try:
        text = (
            f"{SEP}\n"
            f"{center('🤖 GPT Image Bot')}\n"
            f"{SEP}\n\n"
            f"🟢 **Bot Restarted Successfully**\n\n"
            f"📋 Status:\n"
            f"  • 👤 Accounts: {Account.count()}\n"
            f"  • ⏳ Queue pending: {Queue.get_pending_count()}\n"
            f"  • 🔄 Session check: Every 5m\n"
            f"  • ⏰ Limit auto-reset: Every 5m\n\n"
            f"{SEP}\n"
            f"⚙️ *All systems operational*"
        )
        for uid in config.ADMIN_IDS:
            try:
                await telegram_app.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
            except:
                pass
    except:
        pass

    yield

    limit_task.cancel()
    session_task.cancel()
    await telegram_app.updater.stop()
    await telegram_app.stop()
    await telegram_app.shutdown()

async def session_check_loop():
    print("[main] Background session checking disabled for RAM optimization")
    while True:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(60)

async def limit_reset_loop():
    while True:
        try:
            await asyncio.sleep(LIMIT_RESET_INTERVAL * 60)
            n = reset_limited_accounts()
            if n > 0 and telegram_app:
                text = (
                    f"{SEP}\n"
                    f"{center('🔄 Limit Reset')}\n"
                    f"{SEP}\n\n"
                    f"✅ **{n} account(s) restored!**\n"
                    f"⏰ Their limit has expired.\n"
                    f"📥 Ready for image generation.\n\n"
                    f"{SEP}"
                )
                for uid in config.ADMIN_IDS:
                    try:
                        await telegram_app.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
                    except:
                        pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[limit_reset] Error: {e}")
            await asyncio.sleep(60)

app = FastAPI(lifespan=lifespan, title="GPT Image Bot", docs_url=None, redoc_url=None)

# CORS - Allow extension to push cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "ok", "bot": "GPT Image Bot by TurabCoder"}

@app.get("/api/status")
async def api_status():
    ac = Account.count()
    q = Queue.stats()
    return {"accounts": ac, "queue": q}

@app.get("/api/generate")
async def api_generate(prompt: str = "", image_size: str = "1:1"):
    if not prompt:
        return {"success": False, "error": "Missing prompt"}
    result = await call_remote_worker("/process", {"prompt": prompt, "image_size": image_size})
    return result

@app.post("/api/cookies")
async def receive_cookies(request: Request):
    if API_KEY:
        key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(key, API_KEY):
            raise HTTPException(401, "Invalid API Key")

    body = await request.json()
    cookies = body.get("cookies", [])
    if not cookies:
        raise HTTPException(400, "No cookies provided")

    client_ip = request.client.host if request.client else "unknown"
    label = body.get("label", f"ext-{client_ip}-{len(cookies)}ck")
    profile_name = body.get("profile_name", label)
    print(f"[api] Cookies received: label={label} count={len(cookies)} ip={client_ip}")

    from worker.entry import process_account_entry
    ok, msg = process_account_entry(cookies, source="extension", label=label)
    if ok:
        accounts_col.update_one({"label": label}, {"$set": {"profile_name": profile_name, "last_updated": datetime.now(timezone.utc)}})
        return {"success": True, "message": msg, "label": label}
    return {"success": False, "error": msg}

@app.get("/api/accounts")
async def list_accounts():
    docs = Account.get_all()
    return [
        {
            "id": str(d["_id"]),
            "label": d.get("label", "?"),
            "profile_name": d.get("profile_name", d.get("label", "?")),
            "source": d.get("source", "manual"),
            "expired": d.get("expired", False),
            "limited": d.get("limited", False),
            "limit_reset_at": str(d.get("limit_reset_at", "")) if d.get("limit_reset_at") else None,
            "limit_hit_at": str(d.get("limit_hit_at", "")) if d.get("limit_hit_at") else None,
            "first_loaded_at": str(d.get("first_loaded_at", "")) if d.get("first_loaded_at") else None,
            "error_count": d.get("error_count", 0),
            "created_at": str(d.get("created_at", "")),
        }
        for d in docs
    ]

@app.get("/api/accounts/<label>/refresh")
async def refresh_cookies(label: str):
    doc = accounts_col.find_one({"label": label})
    if not doc:
        raise HTTPException(404, "Account not found")
    accounts_col.update_one(
        {"_id": doc["_id"]},
        {"$set": {"expired": False, "limited": False, "limit_reset_at": None, "limit_hit_at": None, "error_count": 0}}
    )
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    
    # Enforce Heroku-like 512MB RAM limit locally for testing
    try:
        import resource
        mem_limit_mb = 512
        limit_bytes = mem_limit_mb * 1024 * 1024
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, hard))
        print(f"🔒 Local memory limit restricted to {mem_limit_mb} MB (matching Heroku constraints)")
    except Exception as e:
        print(f"⚠️ Could not set memory limit: {e}")

    # Enable headful mode locally when running directly
    os.environ["DEBUG"] = "true"
    print("🚀 Starting GPT-Image-Bot locally...")
    print("💡 Browser will open automatically (DEBUG=true)")
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
