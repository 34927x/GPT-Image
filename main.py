import asyncio, os, sys, json, hmac, hashlib
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

import config
from db import init_db, queue_col, accounts_col
from models import Queue, Account
from bot import (start, menu_command, gen_command, button_handler,
                 handle_text, handle_file, process_queue, status_command)
from accounts.manager import reset_limited_accounts

telegram_app = None
API_KEY = os.getenv("API_KEY", "")
SESSION_CHECK_INTERVAL = int(os.getenv("SESSION_CHECK_INTERVAL", "30"))
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
    await telegram_app.updater.start_polling()

    session_task = asyncio.create_task(session_check_loop())
    limit_task = asyncio.create_task(limit_reset_loop())

    try:
        text = (
            "━━━━━━━━━━━━━━━━━━━\n"
            "🤖 *GPT Image Bot*\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "🟢 **Bot Restarted Successfully**\n\n"
            "📋 Status:\n"
            f"• 👤 Accounts: {Account.count()}\n"
            f"• ⏳ Queue pending: {Queue.get_pending_count()}\n"
            "• 🔄 Session check: Every 30m\n"
            "• ⏰ Limit auto-reset: Every 5m\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚙️ *All systems operational*\n"
            "─────────────────────"
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
    while True:
        try:
            await asyncio.sleep(SESSION_CHECK_INTERVAL * 60)
            from worker import check_session
            expired = await check_session()
            if expired and telegram_app:
                for acct in expired:
                    label = acct.get("profile_name") or acct.get("label", "Unknown")
                    msg = f"⚠️ Session expired: `{label}`\nRe-capture cookies from extension."
                    for uid in config.ADMIN_IDS:
                        try:
                            await telegram_app.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
                        except:
                            pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[session_check] Error: {e}")
            await asyncio.sleep(60)

async def limit_reset_loop():
    while True:
        try:
            await asyncio.sleep(LIMIT_RESET_INTERVAL * 60)
            n = reset_limited_accounts()
            if n > 0 and telegram_app:
                text = (
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🔄 *Limit Reset* ── *Auto* ── *Active*\n"
                    "━━━━━━━━━━━━━━━━━━━\n\n"
                    f"✅ **{n} account(s) restored!**\n"
                    "⏰ Their limit has expired.\n"
                    "📥 Ready for image generation.\n\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "─────────────────────"
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
    from worker import submit_prompt
    result = await submit_prompt(prompt, image_size)
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

    existing = accounts_col.find_one({"label": label})
    if existing:
        accounts_col.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "cookies": cookies,
                "source": "extension",
                "profile_name": profile_name,
                "last_updated": datetime.now(timezone.utc),
                "expired": False,
                "limited": False,
                "limit_reset_at": None,
                "error_count": 0
            }}
        )
        return {"success": True, "action": "updated", "label": label}

    Account.create(label, cookies, source="extension")
    accounts_col.update_one({"label": label}, {"$set": {"profile_name": profile_name}})
    return {"success": True, "action": "created", "label": label}

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
        {"$set": {"expired": False, "limited": False, "limit_reset_at": None, "error_count": 0}}
    )
    return {"success": True}
