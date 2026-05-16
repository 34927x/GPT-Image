import asyncio, traceback
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PwTimeout

from models import Account
from accounts.manager import (
    get_next_account, mark_success, mark_error, mark_expired,
    mark_limited, update_profile_name, parse_limit_reset_time,
)

CHATGPT_URL = "https://chatgpt.com"
IMAGES_URL = "https://chatgpt.com/images"
LOGIN_URL = "https://chatgpt.com/auth/login"

_browser = None

async def get_browser():
    global _browser
    if _browser is None:
        p = await async_playwright().start()
        _browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--single-process", "--disable-accelerated-2d-canvas",
                "--no-first-run", "--disable-web-security",
            ]
        )
    return _browser

async def close():
    global _browser
    if _browser:
        await _browser.close()
        _browser = None

async def new_context(cookies):
    b = await get_browser()
    ctx = await b.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="en-US", timezone_id="America/New_York"
    )
    if cookies:
        await ctx.add_cookies(cookies)
    return ctx

async def capture_profile_name(p):
    NAME_SELECTORS = [
        '[data-testid="user-avatar"] img[alt]',
        '[data-testid="profile-name"]',
        'nav button span.truncate',
        'nav button div.truncate',
        '[data-testid="user-menu"] span',
        'header button span.truncate',
        'nav a div.truncate',
    ]
    body = await p.text_content("body") or ""
    for sel in NAME_SELECTORS:
        try:
            el = await p.query_selector(sel)
            if el:
                txt = (await el.text_content() or "").strip()
                if txt:
                    return txt
        except:
            pass
    import re as _re
    m = _re.search(r'"user_name"\s*:\s*"([^"]+)"', body)
    if m:
        return m.group(1)
    m = _re.search(r'"name"\s*:\s*"([^"]+)"', body)
    if m:
        return m.group(1)
    return None

async def wait_stable(page, timeout_sec=8):
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_sec*1000)
    except:
        pass
    await asyncio.sleep(2)

CREATE_BTN_SELECTORS = [
    'button:has-text("Create")',
    'button:has-text("New image")',
    'button:has-text("New")',
    'a:has-text("Create")',
    '[data-testid="create-button"]',
    'button[aria-label*="Create"]',
    'button:has(svg.lucide-plus)',
]

async def ensure_prompt_visible(p):
    body = await p.text_content("body") or ""
    LOGIN_URL = "https://chatgpt.com/auth/login"
    if LOGIN_URL in p.url:
        return False

    PROMPT_SEL = [
        '#prompt-textarea',
        'textarea',
        '[contenteditable="true"]',
        'div[contenteditable="true"]',
        '[data-message-author-role]',
    ]
    for sel in PROMPT_SEL:
        try:
            el = await p.wait_for_selector(sel, timeout=5000)
            if el and await el.is_visible():
                return True
        except:
            pass

    await p.screenshot(path="/tmp/worker-no-prompt-initial.png")

    for btn_sel in CREATE_BTN_SELECTORS:
        try:
            btn = await p.query_selector(btn_sel)
            if btn and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(3)
                await wait_stable(p)
                for sel in PROMPT_SEL:
                    try:
                        el = await p.wait_for_selector(sel, timeout=5000)
                        if el and await el.is_visible():
                            return True
                    except:
                        pass
        except:
            pass

    try:
        await p.keyboard.press("/")
        await asyncio.sleep(2)
        for sel in PROMPT_SEL:
            try:
                el = await p.wait_for_selector(sel, timeout=3000)
                if el and await el.is_visible():
                    return True
            except:
                pass
    except:
        pass

    return False

async def login(account, cb=None):
    ctx = await new_context(account["cookies"])
    p = await ctx.new_page()

    try:
        LOGIN_CHECK = "https://chatgpt.com/auth/login"
        await p.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=30000)
    except PwTimeout:
        await ctx.close()
        return None, None

    await asyncio.sleep(3)
    if LOGIN_URL in p.url:
        mark_expired(account["_id"])
        await ctx.close()
        return None, None

    if cb:
        await cb("📍 Opening Images page...")
    try:
        await p.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
    except:
        pass
    await wait_stable(p, timeout_sec=10)

    name = await capture_profile_name(p)
    if name:
        update_profile_name(account["_id"], name)

    return p, ctx

GENERATE_BTN_SELECTORS = [
    '[data-testid="send-button"]',
    'button[type="submit"]',
    'button:has(svg.lucide-arrow-up)',
    'button[aria-label*="Send"]',
    'button:has-text("Generate")',
    'button:has-text("Send")',
]

IMAGE_SELECTORS = [
    'img[src*="dalle"]',
    'img[src*="oaidalle"]',
    'img[src*="gpt-image"]',
    'img[alt*="DALL"]',
    'img[alt*="Generated"]',
    'img[src*="image"]',
]

STOP_SELECTORS = [
    '[data-testid="stop-button"]',
    'button:has(svg.lucide-square)',
    'button[aria-label="Stop"]',
    'button:has-text("Stop")',
]

async def find_visible(page, selectors, timeout=10000):
    for sel in selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=3000)
            if el and await el.is_visible():
                return el
        except:
            continue
    try:
        el = await page.wait_for_selector(selectors[0], timeout=timeout)
        return el
    except:
        return None

def display_name(account):
    return account.get("profile_name") or account.get("label", "Account")

async def submit_prompt(prompt, image_size="1:1", retry=5, progress_callback=None):
    for attempt in range(retry):
        account = get_next_account()
        if not account:
            if progress_callback:
                await progress_callback("❌ No valid accounts available")
            return {"success": False, "error": "No valid accounts"}

        name = display_name(account)

        if progress_callback:
            await progress_callback(f"🔄 Attempt {attempt+1} — `{name}`")

        p, ctx = await login(account, cb=progress_callback)
        if p is None:
            mark_error(account["_id"])
            if progress_callback:
                await progress_callback("⚠️ Session expired, trying next...")
            continue

        if progress_callback:
            await progress_callback(f"✅ Logged in as `{name}`")

        for dismiss_sel in [
            'button:has-text("Stay logged out")',
            'button:has-text("Continue")',
            '[aria-label="Close"]', '.btn-close',
            'button:has-text("Dismiss")',
            'button:has-text("Got it")',
            'button:has-text("Okay")',
        ]:
            try:
                btn = await p.query_selector(dismiss_sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(1)
            except:
                pass

        await wait_stable(p)

        if not await ensure_prompt_visible(p):
            await p.screenshot(path="/tmp/worker-prompt-fail.png")
            await ctx.close()
            mark_error(account["_id"])
            if progress_callback:
                await progress_callback("⚠️ No prompt input found, rotating...")
            continue

        try:
            ta = await find_visible(p, [
                '#prompt-textarea', 'textarea', '[contenteditable="true"]',
                'div[contenteditable="true"]', '[data-message-author-role]',
            ], timeout=5000)
            if not ta:
                raise Exception("Prompt not found after ensure")

            await ta.click()
            await asyncio.sleep(0.5)
            await ta.fill("")
            await asyncio.sleep(0.3)
            await p.keyboard.type(prompt, delay=10)
            await asyncio.sleep(1)

            send_btn = await find_visible(p, GENERATE_BTN_SELECTORS, timeout=5000)
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
                await ctx.close()
                if progress_callback:
                    await progress_callback(f"✅ Done on `{name}`")
                return {"success": True, "image_url": image_url, "account": name}

            body = await p.text_content("body") or ""

            reset_at = parse_limit_reset_time(body)
            if reset_at:
                mark_limited(account["_id"], reset_at)
                await ctx.close()
                left = (reset_at - datetime.now(timezone.utc)).total_seconds()
                h = int(left // 3600)
                m = int((left % 3600) // 60)
                if progress_callback:
                    await progress_callback(f"⏳ `{name}` limit — resets in {h}h {m}m, rotating...")
                continue

            await p.screenshot(path="/tmp/worker-no-image.png")
            await ctx.close()
            if progress_callback:
                await progress_callback("❌ No image generated")
            return {"success": False, "error": "No image generated"}

        except Exception as e:
            mark_error(account["_id"])
            try:
                await p.screenshot(path=f"/tmp/worker-error-{attempt}.png")
            except:
                pass
            try:
                await ctx.close()
            except:
                pass
            if progress_callback:
                await progress_callback(f"⚠️ {str(e)[:60]}... rotating")
            continue

    return {"success": False, "error": "All accounts exhausted"}

async def wait_for_image(p, timeout=180000):
    deadline = asyncio.get_event_loop().time() + (timeout / 1000)
    while asyncio.get_event_loop().time() < deadline:
        img = await find_visible(p, IMAGE_SELECTORS, timeout=15000)
        if img:
            return await img.get_attribute("src")
        body = await p.text_content("body") or ""
        if parse_limit_reset_time(body):
            return None
        stop_btn = await find_visible(p, STOP_SELECTORS, timeout=3000)
        if not stop_btn:
            break
        await asyncio.sleep(2)
    return None

async def check_session():
    docs = Account.get_all()
    expired = []
    for d in docs:
        if d.get("expired"):
            expired.append(d)
            continue
        try:
            b = await get_browser()
            ctx = await new_context(d["cookies"])
            p = await ctx.new_page()
            await p.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)
            if LOGIN_URL in p.url:
                mark_expired(d["_id"])
                expired.append(d)
            await ctx.close()
        except Exception:
            try:
                await ctx.close()
            except:
                pass
    return expired
