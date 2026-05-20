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
