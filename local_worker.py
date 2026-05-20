"""
LOCAL CHROMIUM WORKER — runs on your local machine.

This standalone FastAPI server exposes endpoints that Heroku calls
to generate images via Playwright + Chromium on ChatGPT.

Usage:
    pip install -r requirements-local.txt
    playwright install chromium
    python local_worker.py

The Heroku bot sends HTTP requests here for image generation.
"""
import asyncio, os, re, io, json, sys
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# ── Config ──
WORKER_SECRET = os.getenv("WORKER_SECRET", "change_me_secret")
WORKER_PORT = int(os.getenv("WORKER_PORT", "8888"))
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB = os.getenv("MONGO_DB", "gpt_rotator")

# ── MongoDB ──
from pymongo import MongoClient

_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsInsecure=True)
db = _client[MONGO_DB]
accounts_col = db["accounts"]

# ── Import all worker internals ──
# We import the actual Playwright logic from worker.py
# Add parent dir to path so we can import worker module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worker import (
    get_next_account, display_name, ensure_logged_in, ensure_browser,
    close_browser, dismiss_popups, ensure_prompt_visible, find_visible,
    wait_for_image, mark_error, mark_success, mark_expired, mark_limited,
    parse_limit_reset_time, reset_limited_accounts, worker_lock,
    _pc, _master,
    PROMPT_SELECTORS, GENERATE_BTN_SELECTORS, IMAGES_URL,
)


# ── Auth middleware ──
def verify_secret(request: Request):
    key = request.headers.get("X-Worker-Secret", "")
    if key != WORKER_SECRET:
        raise HTTPException(status_code=401, detail="Invalid worker secret")


# ── Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[local_worker] Starting on port {WORKER_PORT}")
    print(f"[local_worker] MongoDB: {MONGO_DB}")
    try:
        _client.admin.command('ping')
        print("[local_worker] MongoDB connected ✅")
    except Exception as e:
        print(f"[local_worker] MongoDB ping failed: {e}")

    acct_count = accounts_col.count_documents({})
    print(f"[local_worker] {acct_count} accounts in DB")

    # Start limit reset background task
    limit_task = asyncio.create_task(limit_reset_loop())

    yield

    limit_task.cancel()
    await close_browser()
    print("[local_worker] Shutdown complete")


async def limit_reset_loop():
    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes
            n = reset_limited_accounts()
            if n > 0:
                print(f"[local_worker] Reset {n} limited account(s)")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[local_worker] Limit reset error: {e}")
            await asyncio.sleep(60)


app = FastAPI(lifespan=lifespan, title="GPT Image Local Worker", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "GPT Image Local Worker"}


@app.get("/health")
async def health():
    acct_count = accounts_col.count_documents({})
    active = accounts_col.count_documents({"expired": {"$ne": True}, "limited": {"$ne": True}})
    return {
        "status": "healthy",
        "accounts_total": acct_count,
        "accounts_available": active,
    }


@app.post("/process")
async def process_prompt(request: Request):
    """Process a single prompt — called by Heroku bot."""
    verify_secret(request)
    body = await request.json()
    prompt = body.get("prompt", "")
    image_size = body.get("image_size", "1:1")
    retry = body.get("retry", 5)

    if not prompt:
        return {"success": False, "error": "Missing prompt"}

    # Use the existing submit_prompt logic but inline here
    # to avoid the finally: close_browser() which kills persistence
    result = await _process_single(prompt, image_size, retry)
    return result


@app.post("/process-bulk")
async def process_bulk(request: Request):
    """Process multiple prompts in one session — called by Heroku bot."""
    verify_secret(request)
    body = await request.json()
    prompts = body.get("prompts", [])
    image_size = body.get("image_size", "1:1")
    retry = body.get("retry", 5)

    if not prompts:
        return {"results": [], "error": "No prompts"}

    results = await _process_bulk(prompts, image_size, retry)
    return {"results": results}


# ── Core processing (reuses worker.py logic but WITHOUT closing browser after each call) ──

async def _process_single(prompt, image_size="1:1", retry=5):
    """Process a single prompt. Keeps browser alive between calls for speed."""
    async with worker_lock:
        print(f"[local_worker] Processing: '{prompt[:50]}...' size={image_size}")
        try:
            for attempt in range(retry):
                account = get_next_account()
                if not account:
                    return {"success": False, "error": "No valid accounts"}

                if account.get("_limited_info"):
                    limited = account["accounts"]
                    first = limited[0]
                    h, m = first["hours_left"], first["minutes_left"]
                    return {
                        "success": False,
                        "error": f"All accounts limited — resets in {h}h {m}m",
                        "limited_accounts": limited,
                    }

                name = display_name(account)
                print(f"[local_worker] Attempt {attempt+1} — {name}")

                logged_in = await ensure_logged_in(account)
                if not logged_in:
                    mark_error(account["_id"])
                    print(f"[local_worker] {name} login failed")
                    continue

                print(f"[local_worker] Logged in as {name}")

                try:
                    ctx = _master["ctx"]
                    page = _master["page"]

                    await page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(3)
                    await dismiss_popups(page)

                    if not await ensure_prompt_visible(page):
                        print(f"[local_worker] Prompt not visible for {name}")
                        mark_error(account["_id"])
                        continue

                    ta = await find_visible(page, PROMPT_SELECTORS, timeout=5000)
                    if not ta:
                        continue

                    await ta.click(click_count=3)
                    await asyncio.sleep(0.3)
                    await page.keyboard.type(prompt, delay=10)
                    await asyncio.sleep(1)

                    send_btn = await find_visible(page, GENERATE_BTN_SELECTORS, timeout=5000)
                    if send_btn:
                        await send_btn.click()
                    else:
                        await page.keyboard.press("Enter")

                    await asyncio.sleep(3)

                    image_url = await wait_for_image(page)

                    if image_url:
                        mark_success(account["_id"])
                        print(f"[local_worker] IMAGE: {image_url[:80]}...")
                        # Save updated cookies
                        try:
                            updated_cookies = await ctx.cookies()
                            if updated_cookies:
                                accounts_col.update_one(
                                    {"_id": account["_id"]},
                                    {"$set": {"cookies": updated_cookies}}
                                )
                        except Exception:
                            pass
                        return {"success": True, "image_url": image_url, "account": name}

                    body = await page.text_content("body") or ""
                    reset_at = parse_limit_reset_time(body)
                    if reset_at:
                        mark_limited(account["_id"], reset_at)
                        left = (reset_at - datetime.now(timezone.utc)).total_seconds()
                        h, m = int(left // 3600), int((left % 3600) // 60)
                        print(f"[local_worker] {name} limit — resets in {h}h {m}m")
                        continue

                    return {"success": False, "error": "No image generated"}

                except Exception as e:
                    print(f"[local_worker] Exception on {name}: {e}")
                    import traceback
                    traceback.print_exc()
                    mark_error(account["_id"])
                    continue

            return {"success": False, "error": "All accounts exhausted"}
        except Exception as e:
            print(f"[local_worker] Fatal error: {e}")
            import traceback
            traceback.print_exc()
            # On fatal error, clean up browser
            await close_browser()
            return {"success": False, "error": f"Fatal: {str(e)[:100]}"}


async def _process_bulk(prompts, image_size="1:1", retry=5):
    """Process multiple prompts in a single session."""
    async with worker_lock:
        print(f"[local_worker] Bulk: {len(prompts)} prompts, size={image_size}")
        try:
            for attempt in range(retry):
                account = get_next_account()
                if not account:
                    return [{"success": False, "error": "No accounts"} for _ in prompts]

                name = display_name(account)
                print(f"[local_worker] Bulk attempt {attempt+1} — {name}")

                logged_in = await ensure_logged_in(account)
                if not logged_in:
                    mark_error(account["_id"])
                    continue

                print(f"[local_worker] Logged in as {name}")

                try:
                    ctx = _master["ctx"]
                    page = _master["page"]

                    results = []
                    limit_hit = False

                    for i, prompt in enumerate(prompts):
                        if limit_hit:
                            results.append({"success": False, "error": "Limit reached (previous)"})
                            continue

                        print(f"[local_worker] Bulk [{i+1}/{len(prompts)}]: {prompt[:40]}...")

                        try:
                            await page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
                            await asyncio.sleep(3)
                            await dismiss_popups(page)

                            if not await ensure_prompt_visible(page):
                                results.append({"success": False, "error": "Prompt input not found"})
                                continue

                            ta = await find_visible(page, PROMPT_SELECTORS, timeout=5000)
                            if not ta:
                                results.append({"success": False, "error": "Prompt not found"})
                                continue

                            await ta.click(click_count=3)
                            await asyncio.sleep(0.3)
                            await page.keyboard.type(prompt, delay=10)
                            await asyncio.sleep(1)

                            send_btn = await find_visible(page, GENERATE_BTN_SELECTORS, timeout=5000)
                            if send_btn:
                                await send_btn.click()
                            else:
                                await page.keyboard.press("Enter")

                            await asyncio.sleep(3)
                            image_url = await wait_for_image(page)

                            if image_url:
                                results.append({"success": True, "image_url": image_url, "account": name})
                                mark_success(account["_id"])
                                try:
                                    updated_cookies = await ctx.cookies()
                                    if updated_cookies:
                                        accounts_col.update_one(
                                            {"_id": account["_id"]},
                                            {"$set": {"cookies": updated_cookies}}
                                        )
                                except Exception:
                                    pass
                            else:
                                body_text = await page.text_content("body") or ""
                                reset_at = parse_limit_reset_time(body_text)
                                if reset_at:
                                    mark_limited(account["_id"], reset_at)
                                    results.append({"success": False, "error": "Limit reached"})
                                    limit_hit = True
                                else:
                                    results.append({"success": False, "error": "No image"})

                        except Exception as e:
                            results.append({"success": False, "error": str(e)[:60]})

                    return results

                except Exception as e:
                    print(f"[local_worker] Bulk exception on {name}: {e}")
                    return [{"success": False, "error": f"Exception: {str(e)[:60]}"} for _ in prompts]

            return [{"success": False, "error": "All accounts exhausted"} for _ in prompts]
        except Exception as e:
            print(f"[local_worker] Fatal bulk error: {e}")
            await close_browser()
            return [{"success": False, "error": f"Fatal: {str(e)[:100]}"} for _ in prompts]


if __name__ == "__main__":
    import uvicorn
    print("🖥️  GPT Image Local Worker")
    print(f"📡 Starting on port {WORKER_PORT}")
    print(f"🔐 Secret: {'***' + WORKER_SECRET[-4:] if len(WORKER_SECRET) > 4 else '(too short!)'}")
    print("─" * 40)

    uvicorn.run("local_worker:app", host="0.0.0.0", port=WORKER_PORT, reload=False)
