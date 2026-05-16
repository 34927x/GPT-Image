"""
Styled message builder — consistent boxed formatting for all bot messages.
"""

SEP = "━━━━━━━━━━━━━━━━━━━"
END = "════════════════════"

def box(title, body, emoji="🤖", credit=True):
    lines = [
        SEP,
        f"{emoji} *{title}*",
        "",
        body,
        SEP
    ]
    if credit:
        lines += ["", END, "_by @TurabCoder_"]
    return "\n".join(lines)

def error_box(title="Oops!", body="Something went wrong.", reasons=None, tips=None):
    if reasons is None:
        reasons = ["Server busy", "Network issue", "Temporary glitch"]
    if tips is None:
        tips = ["Try again in a few moments", "Check your internet"]
    lines = [
        f"😕 *{title}*",
        "",
        body,
        "",
        SEP,
        "🛠 Possible Reasons:"
    ]
    for r in reasons:
        lines.append(f"• {r}")
    lines += [
        "",
        SEP,
        "💡 What You Can Do:"
    ]
    for t in tips:
        lines.append(f"🔄 {t}")
    lines += [
        "",
        SEP,
        "🆘 Support: @TurabCoder",
        "⏰ Status: Temporary Issue",
        "🔐 Your data is safe",
        END
    ]
    return "\n".join(lines)

def menu_header(title="📌 Menu"):
    return f"{SEP}\n{title}\n{SEP}"

def queue_box(prompt, image_size, batch_info=""):
    lines = [
        SEP,
        "🖼️ *Generating*",
        "",
        f"`{prompt[:40]}`{batch_info}",
        "───",
        f"📐 Size: {image_size}",
        SEP
    ]
    return "\n".join(lines)

def progress_box(prompt, step, batch_info=""):
    lines = [
        SEP,
        f"🖼️ `{prompt[:40]}`{batch_info}",
        "───",
        step,
        SEP
    ]
    return "\n".join(lines)

def result_box(prompt, image_url, batch_info=""):
    lines = [
        f"✅ *Done*",
        "",
        f"`{prompt[:100]}`{batch_info}",
        "",
        SEP,
        f"📎 {image_url}",
        END,
        "_by @TurabCoder_"
    ]
    return "\n".join(lines)

def status_box(accounts, pending, processing, done, failed, sessions):
    lines = [
        SEP,
        "📊 *Bot Status*",
        "",
        f"👤 Accounts: {accounts}",
        f"⏳ Pending: {pending}",
        f"🔄 Processing: {processing}",
        f"✅ Done: {done}",
        f"❌ Failed: {failed}",
        "",
        SEP,
        "🔹 Sessions"
    ]
    for s in sessions[:5]:
        lines.append(f"• {s}")
    lines += [SEP, END, "_by @TurabCoder_"]
    return "\n".join(lines)

def accounts_box(entries):
    lines = [
        SEP,
        "👤 *Accounts*",
        ""
    ]
    if not entries:
        lines += ["No accounts yet.", SEP, END, "_by @TurabCoder_"]
        return "\n".join(lines)
    for e in entries:
        lines.append(e)
    lines += [SEP, END, "_by @TurabCoder_"]
    return "\n".join(lines)

def queued_box(prompt, size, count, position):
    lines = [
        SEP,
        "✅ *Queued Successfully*",
        "",
        f"Prompt: `{prompt}`",
        f"Size: {size}",
        f"Count: {count}",
        f"Position: #{position}",
        "",
        SEP,
        "⏳ I'll send images here",
        "    as they're generated!",
        END,
        "_by @TurabCoder_"
    ]
    return "\n".join(lines)

def help_box():
    lines = [
        SEP,
        "🤖 *GPT Bot Guide*",
        "",
        "Send any text to generate",
        "Upload .txt for bulk prompts",
        "",
        SEP,
        "📋 *Commands*",
        "• /menu — Full menu",
        "• /gen <prompt> — Generate",
        "• /status — Bot status",
        "",
        SEP,
        "💡 Tips",
        "• Blank line = new prompt",
        "• .txt file = bulk upload",
        "",
        END,
        "_by @TurabCoder_"
    ]
    return "\n".join(lines)

def image_caption(prompt, batch_info=""):
    return (
        f"✅ *{prompt[:100]}*{batch_info}\n\n"
        f"_by @TurabCoder_"
    )
