"""
Worker: Playwright headless ChatGPT automation

Login flow (v2 — extension auto-sends cookies to MongoDB):
1. Chrome extension captures cookies from chatgpt.com
2. Extension POSTs cookies to FastAPI endpoint (POST /api/cookies)
3. Saved in MongoDB accounts collection
4. Worker reads account from DB → injects cookies → validates session
5. Each prompt opens in a FRESH new chat (navigate to / or click New Chat)
6. If session expired → marks expired → admin notified

Token refresh: WE DON'T REFRESH. We DETECT expiry and alert admin.
Admin re-captures cookies from extension (which auto-sends to DB).
"""

import asyncio, re, traceback
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PwTimeout

import config
from models import Account, Queue, Session
from accounts.manager import get_next_account, mark_success, mark_error, mark_expired
from utils.helpers import make_image_filename

CHATGPT_URL = "https://chatgpt.com"
LOGIN_URL = "https://chatgpt.com/auth/login"

browser = None
cached_context = None
cached_page = None

async def get_browser():
    global browser
    if browser is None:
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--disable-web-security",
            ]
        )
    return browser

async def new_context(cookies):
    b = await get_browser()
    ctx = await b.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/New_York"
    )
    if cookies:
        await ctx.add_cookies(cookies)
    return ctx

async def login(account):
    """Load account cookies, return page. Returns None if expired."""
    global cached_context, cached_page
    if cached_context:
        await cached_context.close()
    cached_context = await new_context(account["cookies"])
    cached_page = await cached_context.new_page()

    try:
        await cached_page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=30000)
    except PwTimeout:
        return None

    await asyncio.sleep(3)
    if LOGIN_URL in cached_page.url:
        mark_expired(account["_id"])
        return None

    # Fresh new chat per account
    try:
        new_chat_btn = await cached_page.query_selector(
            'a[href="/"], nav a:has(svg), button:has-text("New Chat"), [data-testid="new-chat-button"]'
        )
        if new_chat_btn:
            await new_chat_btn.click()
            await asyncio.sleep(2)
        else:
            await cached_page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
    except Exception:
        await cached_page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(2)

    return cached_page

async def step_log(page, step_msg, progress_msg):
    """Log a step and update the progress message if provided."""
    print(f"[worker] {step_msg}")
    return step_msg

async def wait_for_image(p, timeout=120000):
    deadline = asyncio.get_event_loop().time() + (timeout / 1000)
    while asyncio.get_event_loop().time() < deadline:
        try:
            img = await p.wait_for_selector(
                'img[src*="dalle"], img[src*="oaidalle"], img[src*="gpt-image"]',
                timeout=15000
            )
            if img:
                return await img.get_attribute("src")
        except PwTimeout:
            pass
        stop_btn = await p.query_selector(
            'button[data-testid="stop-button"], button:has(svg.lucide-square)'
        )
        if not stop_btn:
            break
        await asyncio.sleep(2)
    return None

async def submit_prompt(prompt, image_size="1:1", retry=2, progress_callback=None):
    """
    Main generation function.
    Opens fresh chat per account → fills prompt → sends → waits for image.
    progress_callback(msg: str) called at each step for live UI updates.
    """
    if progress_callback:
        await progress_callback("🔍 Finding available account...")

    for attempt in range(retry):
        account = get_next_account()
        if not account:
            if progress_callback:
                await progress_callback("❌ No valid accounts available")
            return {"success": False, "error": "No valid accounts"}

        if progress_callback:
            await progress_callback(f"🔄 Logged in as `{account.get('label', 'Account')}`")

        p = await login(account)
        if p is None:
            mark_error(account["_id"])
            if progress_callback:
                await progress_callback(f"⚠️ Session expired, trying next account...")
            continue

        if progress_callback:
            await progress_callback(f"✍️ Sending prompt...")

        try:
            ta = await p.wait_for_selector("#prompt-textarea", timeout=10000)
            await ta.click()
            await ta.select_text()
            await asyncio.sleep(0.5)
            await p.keyboard.type(prompt, delay=20)
            await asyncio.sleep(1)

            send_btn = await p.query_selector(
                '[data-testid="send-button"], button:has(svg.lucide-arrow-up)'
            )
            if send_btn:
                await send_btn.click()
            else:
                await p.keyboard.press("Enter")

            await asyncio.sleep(3)

            if progress_callback:
                await progress_callback(f"⏳ Generating image...")

            image_url = await wait_for_image(p)

            if image_url:
                mark_success(account["_id"])
                if progress_callback:
                    await progress_callback(f"✅ Image generated on `{account.get('label', 'Account')}`")
                return {"success": True, "image_url": image_url, "account": account.get("label")}

            body = await p.text_content("body") or ""
            if "rate" in body.lower() or "too many" in body.lower() or "429" in body:
                mark_error(account["_id"])
                if progress_callback:
                    await progress_callback(f"⚠️ Rate limited, rotating account...")
                if attempt < retry - 1:
                    await asyncio.sleep(5)
                    continue
                return {"success": False, "error": "Rate limited on all accounts"}

            if progress_callback:
                await progress_callback(f"❌ No image generated")
            return {"success": False, "error": "No image generated"}

        except Exception as e:
            mark_error(account["_id"])
            tb = traceback.format_exc()
            if progress_callback:
                await progress_callback(f"⚠️ Error: {str(e)[:60]}... retrying")
            if attempt < retry - 1:
                await asyncio.sleep(3)
                continue
            return {"success": False, "error": str(e)[:200]}

    return {"success": False, "error": "All attempts exhausted"}

async def check_session():
    """Validate all account sessions."""
    docs = Account.get_all()
    expired = []
    for d in docs:
        if d.get("expired"):
            expired.append(d)
            continue
        p = await login(d)
        if p is None:
            mark_expired(d["_id"])
            expired.append(d)
        if cached_context:
            await cached_context.close()
        if cached_page:
            await cached_page.close()
    return expired

async def close():
    global browser, cached_context, cached_page
    if cached_context:
        await cached_context.close()
    if browser:
        await browser.close()
