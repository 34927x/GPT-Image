SEP = "━━━━━━━━━━━━━━━━━━━"
DIV = "─────────────────────"
END = "═══════════════════════"

def box(title, body, emoji="🤖", credit=True):
    lines = [
        SEP,
        f"{emoji} *{title}*",
        DIV,
        body,
        SEP,
    ]
    if credit:
        lines += [END, "_🤖 Powered by @TurabCoder_"]
    return "\n".join(lines)

def error_box(title="😵‍💫 Oops! Something Went Wrong!", body="An unexpected error occurred.", reasons=None, tips=None):
    if reasons is None:
        reasons = [
            "🌐 Server is busy or under heavy load",
            "🔌 Network connectivity issues detected",
            "⏳ Temporary glitch in the system",
            "🔄 Account session might have expired",
        ]
    if tips is None:
        tips = [
            "🔄 Try again in a few minutes",
            "✅ Check if your accounts are still active",
            "📬 Contact @TurabCoder for support",
            "🔐 Rest assured, your data is safe with us",
        ]
    lines = [
        SEP,
        f"😵‍💫 *{title}*",
        "",
        f"📝 *Error Details:*",
        f"`{body}`",
        "",
        SEP,
        "🔍 *Possible Reasons:*",
    ]
    for r in reasons:
        lines.append(f"   • {r}")
    lines += [
        "",
        SEP,
        "💡 *Recommended Actions:*",
    ]
    for t in tips:
        lines.append(f"   • {t}")
    lines += [
        "",
        SEP,
        "🆘 *Need Help?* → @TurabCoder",
        "⏰ *Status:* Temporary Issue — Auto-Retry Active",
        "🔐 *Security:* Your Data is 100% Safe & Encrypted",
        "📊 *System:* Monitoring & Auto-Recovery Enabled",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def menu_header(title="📌 Main Menu Navigation"):
    lines = [
        SEP,
        f"📍 *{title}*",
        "",
        "👇 Use the buttons below to navigate:",
        SEP,
    ]
    return "\n".join(lines)

def queue_box(prompt, image_size, batch_info=""):
    lines = [
        SEP,
        "🖼️ *🎨 Image Generation In Progress* 🖼️",
        DIV,
        "",
        f"📝 *Prompt:* `{prompt[:60]}`{batch_info}",
        f"📐 *Aspect Ratio:* `{image_size}`",
        "",
        SEP,
        "⏳ *Status:* Queued & Processing...",
        "⚡ *ETA:* Usually 30–90 seconds",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def progress_box(prompt, step, batch_info=""):
    lines = [
        SEP,
        f"🖼️ *🎯 Generating:* `{prompt[:50]}`{batch_info}",
        DIV,
        f"📌 *Current Step:*",
        f"   {step}",
        SEP,
        "⏳ *Please wait while we process your request...*",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def result_box(prompt, image_url, batch_info=""):
    lines = [
        SEP,
        "🎉 *✅ Image Generated Successfully!* 🎉",
        DIV,
        "",
        f"📝 *Prompt:* `{prompt[:100]}`{batch_info}",
        "",
        SEP,
        f"🔗 *Download Link:*",
        f"📎 `{image_url}`",
        "",
        SEP,
        "📤 *Image sent to your chat above!* ⬆️",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def status_box(accounts, pending, processing, done, failed, sessions):
    lines = [
        SEP,
        "📊 *📈 Live Bot Status Dashboard* 📊",
        DIV,
        "",
        "━━ 📋 *Overview* ━━",
        f"   👤 *Total Accounts:* `{accounts}`",
        f"   ⏳ *Pending Queue:* `{pending}`",
        f"   🔄 *Processing Now:* `{processing}`",
        f"   ✅ *Completed:* `{done}`",
        f"   ❌ *Failed:* `{failed}`",
        "",
        SEP,
        "━━ 🔐 *Account Sessions* ━━",
    ]
    for s in sessions[:5]:
        lines.append(f"   • {s}")
    if len(sessions) > 5:
        lines.append(f"   • ... and {len(sessions)-5} more")
    lines += [
        "",
        SEP,
        "━━ ⚙️ *System Info* ━━",
        "   • 🖥️  Auto-Session Check: Every 30m",
        "   • ⏰ Limit Auto-Reset: Every 5m",
        "   • 🔄 Max Retry per Task: 5 accounts",
        "   • 🛡️  Rate Limit Protection: Active",
        "",
        SEP,
        "🔄 *Auto-Recovery:* Enabled for all services",
        "📊 *Monitoring:* Real-time session tracking active",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def accounts_box(entries):
    lines = [
        SEP,
        "👥 *📋 Account Management Panel* 👥",
        DIV,
    ]
    if not entries:
        lines += [
            "",
            "📭 *No Accounts Registered Yet*",
            "",
            "━━ 💡 *Quick Tips* ━━",
            "   • Install the Chrome extension",
            "   • Log in to chatgpt.com",
            "   • Click the extension icon to sync",
            "   • Or add manually via Admin panel",
            SEP,
            END,
            "_🤖 Powered by @TurabCoder_",
        ]
        return "\n".join(lines)
    for e in entries:
        lines.append(f"   {e}")
    lines += [
        "",
        SEP,
        "━━ 📌 *Legend* ━━",
        "   🌐 = Extension    📦 = Manual",
        "   ✅ = Active       ❌ = Expired",
        "   ⏳ = Limit Wait   ⚠️ = Error",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def queued_box(prompt, size, count, position):
    lines = [
        SEP,
        "✅ *📥 Successfully Added to Queue!* ✅",
        DIV,
        "",
        "━━ 📝 *Request Details* ━━",
        f"   • ✏️ *Prompt:* `{prompt}`",
        f"   • 📐 *Size:* `{size}`",
        f"   • 🔢 *Count:* `{count}` image(s)",
        f"   • 🎯 *Position:* `#{position}` in queue",
        "",
        SEP,
        "━━ ⏰ *What Happens Next* ━━",
        "   • 🔄 Auto-processing in background",
        "   • 📬 Images sent here automatically",
        "   • ✅ You'll receive each one as ready",
        "",
        SEP,
        "⚡ *Tip:* You can check /status anytime",
        "📊 *Queue is being processed in real-time*",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def help_box():
    lines = [
        SEP,
        "🤖 *📖 Complete User Guide & Help* 🤖",
        DIV,
        "",
        "━━ 🚀 *Getting Started* ━━",
        "   • 📝 Send any text message → auto-generates image",
        "   • 📁 Upload `.txt` file → bulk prompt processing",
        "   • 🖼️ Images are delivered directly in this chat",
        "",
        SEP,
        "━━ ⌨️ *Available Commands* ━━",
        "   • `/menu` — 📌 Show full navigation menu",
        "   • `/gen <prompt>` — 🖼️ Quick generate",
        "   • `/status` — 📊 Live bot & queue status",
        "   • `/start` — 🚀 Initialize the bot",
        "",
        SEP,
        "━━ 💡 *Pro Tips & Tricks* ━━",
        "   • 🎨 Separate prompts by blank line in `.txt`",
        "   • 📐 Choose aspect ratio that fits your need",
        "   • 🔄 Multiple accounts = faster processing",
        "   • ⏳ Queue handles up to 100 tasks at once",
        "",
        SEP,
        "━━ 🔧 *Troubleshooting* ━━",
        "   • ❌ *Session expired* → Re-sync extension",
        "   • ⏳ *Limit reached* → Wait for auto-reset",
        "   • 🔄 *Stuck on generating* → Admin auto-notified",
        "   • 📬 *Still issues?* → Contact @TurabCoder",
        "",
        SEP,
        "━━ 📌 *Quick Reference* ━━",
        "   • 🎯 Purpose: DALL·E image generation via ChatGPT",
        "   • 👥 Multi-account: Auto-rotate on limits",
        "   • 🔐 Security: Cookie-based, no passwords stored",
        "   • ⚡ Speed: Parallel processing with fallbacks",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def image_caption(prompt, batch_info=""):
    lines = [
        SEP,
        f"🎨 *✨ Image Generated* ✨",
        DIV,
        f"📝 `{prompt[:100]}`{batch_info}",
        "",
        SEP,
        "📥 *Downloaded & Delivered Successfully* ✅",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)
