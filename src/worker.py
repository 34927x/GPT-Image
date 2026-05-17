import asyncio, re, os
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PwTimeout
from playwright_stealth import stealth_async  # Cloudflare bot detection bypass

from models import Account
from db import accounts_col
from accounts.manager import (
    get_next_account, mark_success, mark_error, mark_expired,
    mark_limited, update_profile_name, parse_limit_reset_time,
)

DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# Global lock: only one task uses the browser at a time to prevent crashes
worker_lock = asyncio.Lock()

CHATGPT_URL = "https://chatgpt.com"
IMAGES_URL = "https://chatgpt.com/images"
LOGIN_URL = "https://chatgpt.com/auth/login"

_browser = None

async def get_browser():
    global _browser
    if _browser is None:
        p = await async_playwright().start()
        _browser = await p.chromium.launch(
            headless=not DEBUG_MODE,  # Set DEBUG=true to see browser
            args=[
                "--disable-blink-features=AutomationControlled",  # Cloudflare bypass
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--single-process", "--disable-accelerated-2d-canvas",
                "--no-first-run",
            ]
        )
        if DEBUG_MODE:
            print("[worker] DEBUG MODE: Browser is VISIBLE (not headless)")
            print("[worker] Open DevTools > Application tab to see cookies")
    return _browser

async def close():
    global _browser
    if _browser:
        await _browser.close()
        _browser = None

async def new_context(cookies):
    """Create browser context - optionally with cookies"""
    b = await get_browser()
    ctx = await b.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        locale="en-US", timezone_id="America/New_York"
    )
    if cookies:
        print(f"[worker] new_context: Adding {len(cookies)} cookies (used by check_session)")
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
    m = re.search(r'"user_name"\s*:\s*"([^"]+)"', body)
    if m:
        return m.group(1)
    m = re.search(r'"name"\s*:\s*"([^"]+)"', body)
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

async def dismiss_popups(page):
    """Dismiss ChatGPT random 'Welcome', 'Tips', or cookie popups"""
    for sel in [
        'button:has-text("Okay, let\'s go")',
        'button:has-text("Got it")',
        'button:has-text("Stay logged out")',
        'button:has-text("Continue")',
        'button:has-text("Dismiss")',
        'button:has-text("Okay")',
        '[aria-label="Close"]',
        '.btn-close',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(1)
        except:
            pass

async def login(account, cb=None):
    """Login with step-by-step verification"""
    label = account.get("label", "?")
    print(f"[worker] ========== LOGIN START: {label} ==========")

    # ── Step 1: Launch browser ONLY (no context, no page, no cookies) ──
    print(f"[worker] Step 1: Launch browser process")
    print(f"[worker]   → src/worker.py:188 (get_browser)")
    b = await get_browser()
    print(f"[worker] Step 1: DONE - Browser launched")

    # ── Step 2: Wait 5 seconds ──
    print(f"[worker] Step 2: Wait 5 seconds (no cookies yet)")
    await asyncio.sleep(5)
    print(f"[worker] Step 2: DONE - 5 seconds complete")

    # ── Step 3: Create context + page (NO cookies) ──
    print(f"[worker] Step 3: Create browser context (NO cookies)")
    print(f"[worker]   → src/worker.py:202 (b.new_context)")
    ctx = await b.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        locale="en-US", timezone_id="America/New_York"
    )
    p = await ctx.new_page()
    await stealth_async(p)
    print(f"[worker] Step 3: DONE - Context + page created, NO cookies")

    # ── Step 4: Go to chatgpt.com (no cookies) ──
    print(f"[worker] Step 4: Go to {CHATGPT_URL} (no cookies)")
    try:
        await p.goto(CHATGPT_URL, wait_until="networkidle", timeout=45000)
        print(f"[worker] Step 4: DONE - Page loaded: {p.url}")
    except Exception as e:
        print(f"[worker] Step 4: FAILED - {e}")
        await ctx.close()
        return None, None

    # ── Step 5: Reload page ──
    print(f"[worker] Step 5: Reload page")
    try:
        await p.reload(wait_until="networkidle", timeout=30000)
        print(f"[worker] Step 5: DONE - Page reloaded")
    except Exception as e:
        print(f"[worker] Step 5: FAILED - {e}")
        await ctx.close()
        return None, None

    # ── Step 6: Inject cookies NOW ──
    print(f"[worker] ===== COOKIE INJECTION START =====")
    print(f"[worker] Step 6: Inject cookies into browser context")
    cookies = account.get("cookies", [])
    print(f"[worker] Step 6: Found {len(cookies)} cookies in account data")

    cookie_names = [c.get('name', '?') for c in cookies[:5]]
    print(f"[worker] Step 6: Cookie names: {cookie_names}...")

    if cookies:
        print(f"[worker] Step 6: Calling ctx.add_cookies() at src/worker.py:238")
        await ctx.add_cookies(cookies)
        print(f"[worker] Step 6: DONE - {len(cookies)} cookies injected")
        print(f"[worker]   → Check DevTools > Application > Cookies > chatgpt.com")
    else:
        print(f"[worker] Step 6: FAILED - No cookies in account")
        await ctx.close()
        return None, None

    await asyncio.sleep(3)
    print(f"[worker] ===== COOKIE INJECTION END =====")

    # ── Step 7: Go to chatgpt.com (with cookies) - verify login ──
    print(f"[worker] Step 7: Go to {CHATGPT_URL} (WITH cookies)")
    try:
        await p.goto(CHATGPT_URL, wait_until="networkidle", timeout=45000)
        print(f"[worker] Step 7: DONE - Page loaded: {p.url}")
    except Exception as e:
        print(f"[worker] Step 7: FAILED - {e}")
        await ctx.close()
        return None, None

    await asyncio.sleep(3)
    await dismiss_popups(p)

    current_url = p.url
    print(f"[worker] Checking login status: {current_url}")

    if LOGIN_URL in current_url:
        print(f"[worker] Step 7: FAILED - Session expired (redirected to login)")
        mark_expired(account["_id"])
        await ctx.close()
        return None, None

    print(f"[worker] Step 7: DONE - Login verified")

    # ── Step 8: Go to images page ──
    print(f"[worker] Step 8: Go to {IMAGES_URL}")
    if cb:
        await cb("📍 Opening Images page...")

    try:
        await p.goto(IMAGES_URL, wait_until="networkidle", timeout=30000)
        print(f"[worker] Step 8: DONE - Images page loaded: {p.url}")
    except Exception as e:
        print(f"[worker] Step 8: FAILED - {e}")
        await ctx.close()
        return None, None

    await asyncio.sleep(3)

    name = await capture_profile_name(p)
    if name:
        update_profile_name(account["_id"], name)
        print(f"[worker] Profile name: {name}")

    print(f"[worker] ========== LOGIN COMPLETE: {label} ==========")
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
  async with worker_lock:
    print(f"[worker] submit_prompt called: '{prompt[:50]}...' size={image_size} retry={retry}")
    for attempt in range(retry):
        account = get_next_account()
        if not account:
            print("[worker] NO ACCOUNTS available in DB")
            if progress_callback:
                await progress_callback("❌ No valid accounts available")
            return {"success": False, "error": "No valid accounts"}

        if account.get("_limited_info"):
            limited_accts = account["accounts"]
            acct_names = ", ".join([a["label"] for a in limited_accts])
            first_acct = limited_accts[0]
            h = first_acct["hours_left"]
            m = first_acct["minutes_left"]
            error_msg = f"⏳ Account limit reached — resets in {h}h {m}m"
            print(f"[worker] ALL ACCOUNTS LIMITED: {error_msg}")
            if progress_callback:
                await progress_callback(f"{error_msg} ({acct_names})")
            return {"success": False, "error": error_msg, "limited_accounts": limited_accts}

        name = display_name(account)

        if progress_callback:
            await progress_callback(f"🔄 Attempt {attempt+1} — `{name}`")

        # Step 1: Verify login + Step 2: Navigate to images
        p, ctx = await login(account, cb=progress_callback)
        if p is None:
            mark_error(account["_id"])
            if progress_callback:
                await progress_callback(f"⚠️ `{name}` login failed — skipping, trying next...")
            continue

        if progress_callback:
            await progress_callback(f"✅ Logged in as `{name}`")

        # Debug: print current URL
        print(f"[worker] Current URL before finding prompt: {p.url}")
        await asyncio.sleep(2)

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
                    print(f"[worker] Clicking dismiss button: {dismiss_sel}")
                    await btn.click()
                    await asyncio.sleep(1)
            except:
                pass

        await wait_stable(p)

        print(f"[worker] Checking if prompt is visible...")
        if not await ensure_prompt_visible(p):
            print(f"[worker] ERROR: Prompt not visible, taking screenshot")
            await p.screenshot(path="/tmp/worker-prompt-fail.png")
            await ctx.close()
            mark_error(account["_id"])
            if progress_callback:
                await progress_callback("⚠️ No prompt input found, rotating...")
            continue

        print(f"[worker] Prompt visible, proceeding to type...")

        try:
            ta = await find_visible(p, [
                '#prompt-textarea', 'textarea', '[contenteditable="true"]',
                'div[contenteditable="true"]', '[data-message-author-role]',
            ], timeout=5000)
            if not ta:
                raise Exception("Prompt not found after ensure")

            await ta.click(click_count=3)  # triple-click to select all text
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
                print(f"[worker] IMAGE GENERATED on {name}: {image_url[:80]}...")
                await ctx.close()
                if progress_callback:
                    await progress_callback(f"✅ Done on `{name}`")
                return {"success": True, "image_url": image_url, "account": name}

            body = await p.text_content("body") or ""
            print(f"[worker] No image found. Body snippet: {body[:200]}")

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
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout / 1000)
    while loop.time() < deadline:
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
  async with worker_lock:
    docs = Account.get_all()
    print(f"[worker] check_session: {len(docs)} accounts to verify")
    expired = []
    for d in docs:
        label = d.get("label", "?")
        if d.get("expired"):
            print(f"[worker] check_session: {label} already expired, deleting")
            name = d.get("profile_name") or label
            expired.append({"label": label, "profile_name": name, "deleted": True})
            accounts_col.delete_one({"_id": d["_id"]})
            continue
        ctx = None
        try:
            ctx = await new_context(d["cookies"])
            p = await ctx.new_page()
            await stealth_async(p)
            await p.goto(CHATGPT_URL, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(5)
            await dismiss_popups(p)
            if LOGIN_URL in p.url:
                print(f"[worker] check_session: {label} EXPIRED — redirected to login")
                name = d.get("profile_name") or label
                expired.append({"label": label, "profile_name": name, "deleted": True})
                accounts_col.delete_one({"_id": d["_id"]})
            else:
                print(f"[worker] check_session: {label} OK")
            await ctx.close()
        except Exception as e:
            print(f"[worker] check_session: {label} ERROR — {e}")
            if ctx:
                try:
                    await ctx.close()
                except:
                    pass
    print(f"[worker] check_session done: {len(expired)} expired/deleted")
    return expired

async def submit_bulk(prompts, image_size="1:1", retry=5, progress_callback=None):
    async with worker_lock:
        print(f"[worker] submit_bulk: {len(prompts)} prompts, size={image_size}")
        for attempt in range(retry):
            account = get_next_account()
            if not account:
                if progress_callback:
                    await progress_callback("❌ No valid accounts")
                return [{"success": False, "error": "No accounts"} for _ in prompts]

            name = display_name(account)
            if progress_callback:
                await progress_callback(f"🔄 Attempt {attempt+1} — `{name}`")

            p, ctx = await login(account, cb=progress_callback)
            if p is None:
                mark_error(account["_id"])
                continue

            if progress_callback:
                await progress_callback(f"✅ Logged in as `{name}`")

            results = []
            for i, prompt in enumerate(prompts):
                if progress_callback:
                    await progress_callback(f"📝 `{i+1}/{len(prompts)}`: `{prompt[:40]}...`")

                try:
                    ta = await find_visible(p, [
                        '#prompt-textarea', 'textarea', '[contenteditable="true"]',
                        'div[contenteditable="true"]', '[data-message-author-role]',
                    ], timeout=5000)
                    if not ta:
                        results.append({"success": False, "error": "Prompt input not found"})
                        continue

                    await ta.click(click_count=3)
                    await asyncio.sleep(0.3)
                    await p.keyboard.type(prompt, delay=10)
                    await asyncio.sleep(1)

                    send_btn = await find_visible(p, GENERATE_BTN_SELECTORS, timeout=5000)
                    if send_btn:
                        await send_btn.click()
                    else:
                        await p.keyboard.press("Enter")

                    await asyncio.sleep(3)

                    image_url = await wait_for_image(p)
                    if image_url:
                        results.append({"success": True, "image_url": image_url, "account": name})
                        mark_success(account["_id"])
                    else:
                        results.append({"success": False, "error": "No image"})

                    if i < len(prompts) - 1:
                        await p.goto(IMAGES_URL, wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(2)

                except Exception as e:
                    results.append({"success": False, "error": str(e)[:60]})

            await ctx.close()
            return results

        return [{"success": False, "error": "All accounts exhausted"} for _ in prompts]
