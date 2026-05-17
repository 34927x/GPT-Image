SEP = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DIV = "──────────────────────────────────────"
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
        SEP,
        center(f"{emoji} {title}"),
        DIV,
        body,
        END,
    ]
    if credit:
        lines += ["", "_🤖 Powered by @TurabCoder_"]
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
        center("😵‍💫 Error"),
        DIV,
        "",
        f"📝 `{body}`",
        "",
        DIV,
        "🔍 *Possible Reasons:*",
    ]
    for r in reasons:
        lines.append(f"  • {r}")
    lines += [
        "",
        DIV,
        "💡 *Recommended Actions:*",
    ]
    for t in tips:
        lines.append(f"  • {t}")
    lines += [
        "",
        DIV,
        "🆘 *Need Help?* → @TurabCoder",
        "🔐 *Security:* Your Data is 100% Safe",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def menu_header(title="📌 Main Menu"):
    lines = [
        SEP,
        center(title),
        DIV,
        "",
        "👇 Use the buttons below to navigate:",
        END,
    ]
    return "\n".join(lines)

def queue_box(prompt, image_size, batch_info=""):
    lines = [
        SEP,
        center("🎨 Generating"),
        DIV,
        "",
        f"📝 Prompt: `{prompt[:60]}`{batch_info}",
        f"📐 Aspect Ratio: `{image_size}`",
        "",
        DIV,
        "⏳ Status: Queued & Processing...",
        "⚡ ETA: Usually 30–90 seconds",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def progress_box(prompt, step, batch_info=""):
    lines = [
        SEP,
        center(f"🎯 Generating: `{prompt[:50]}`{batch_info}"),
        DIV,
        "",
        "📌 *Current Step:*",
        f"  {step}",
        "",
        DIV,
        "⏳ Please wait while we process your request...",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def result_box(prompt, image_url, batch_info=""):
    lines = [
        SEP,
        center("✅ Image Generated!"),
        DIV,
        "",
        f"📝 Prompt: `{prompt[:100]}`{batch_info}",
        "",
        DIV,
        "🔗 *Download Link:*",
        f"📎 `{image_url}`",
        "",
        DIV,
        "📤 Image sent to your chat above! ⬆️",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def status_box(accounts, pending, processing, done, failed, sessions):
    lines = [
        SEP,
        center("📊 Live Status"),
        DIV,
        "",
        "📋 *Overview*",
        f"  • 👤 Accounts: `{accounts}`",
        f"  • ⏳ Pending: `{pending}`",
        f"  • 🔄 Processing: `{processing}`",
        f"  • ✅ Completed: `{done}`",
        f"  • ❌ Failed: `{failed}`",
        "",
        DIV,
        "🔐 *Account Sessions*",
    ]
    for s in sessions[:5]:
        lines.append(f"  • {s}")
    if len(sessions) > 5:
        lines.append(f"  • ... and {len(sessions)-5} more")
    lines += [
        "",
        DIV,
        "⚙️ *System*",
        "  • Session Check: Every 30m",
        "  • Limit Reset: Every 5m",
        "  • Max Retry: 5 accounts",
        "  • Rate Limit Protection: Active",
        "",
        DIV,
        "🔄 Auto-Recovery: Enabled",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def accounts_box(entries):
    lines = [
        SEP,
        center("👥 Accounts"),
        DIV,
    ]
    if not entries:
        lines += [
            "",
            "📭 No Accounts Registered Yet",
            "",
            DIV,
            "💡 *Quick Tips*",
            "  • Install the Chrome extension",
            "  • Log in to chatgpt.com",
            "  • Click the extension icon to sync",
            "  • Or add manually via Admin panel",
            END,
            "_🤖 Powered by @TurabCoder_",
        ]
        return "\n".join(lines)
    for e in entries:
        lines.append(f"  {e}")
    lines += [
        "",
        DIV,
        "📌 *Legend*",
        "  🌐 = Extension    📦 = Manual",
        "  ✅ = Active       ❌ = Expired",
        "  ⏳ = Limit Wait   ⚠️ = Error",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def queued_box(prompt, size, count, position):
    lines = [
        SEP,
        center("✅ Added to Queue!"),
        DIV,
        "",
        "📝 *Request Details*",
        f"  • ✏️ Prompt: `{prompt}`",
        f"  • 📐 Size: `{size}`",
        f"  • 🔢 Count: `{count}`",
        f"  • 🎯 Position: `#{position}`",
        "",
        DIV,
        "⏰ *What Happens Next*",
        "  • 🔄 Auto-processing in background",
        "  • 📬 Images sent here automatically",
        "  • ✅ You'll receive each one as ready",
        "",
        DIV,
        "💡 Tip: Check /status anytime",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def help_box():
    lines = [
        SEP,
        center("📖 Help & Guide"),
        DIV,
        "",
        "🚀 *Getting Started*",
        "  • 📝 Send text → auto-generate image",
        "  • 📁 Upload `.txt` → bulk processing",
        "  • 🖼️ Images delivered in this chat",
        "",
        DIV,
        "⌨️ *Commands*",
        "  • /menu — Show navigation menu",
        "  • /gen <prompt> — Quick generate",
        "  • /status — Live bot & queue status",
        "  • /start — Initialize the bot",
        "",
        DIV,
        "💡 *Pro Tips*",
        "  • 🎨 Separate prompts by blank line in `.txt`",
        "  • 📐 Choose aspect ratio that fits",
        "  • 🔄 Multiple accounts = faster processing",
        "  • ⏳ Queue handles up to 100 tasks",
        "",
        DIV,
        "🔧 *Troubleshooting*",
        "  • ❌ Session expired → Re-sync extension",
        "  • ⏳ Limit reached → Wait for auto-reset",
        "  • 📬 Still issues? → @TurabCoder",
        "",
        DIV,
        "📌 *Quick Reference*",
        "  • 🎯 DALL·E image generation via ChatGPT",
        "  • 👥 Multi-account auto-rotate on limits",
        "  • 🔐 Cookie-based, no passwords stored",
        "  • ⚡ Parallel processing with fallbacks",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)

def image_caption(prompt, batch_info=""):
    lines = [
        SEP,
        center("✨ Image Generated"),
        DIV,
        "",
        f"📝 `{prompt[:100]}`{batch_info}",
        "",
        DIV,
        "📥 Downloaded & Delivered ✅",
        END,
        "_🤖 Powered by @TurabCoder_",
    ]
    return "\n".join(lines)
