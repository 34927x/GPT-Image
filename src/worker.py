import asyncio, re, os
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PwTimeout
from playwright_stealth import stealth_async

from models import Account
from db import accounts_col
from accounts.manager import (
    get_next_account, mark_success, mark_error, mark_expired,
    mark_limited, update_profile_name, parse_limit_reset_time,
)

worker_lock = asyncio.Lock()

CHATGPT_URL = "https://chatgpt.com"
IMAGES_URL = "https://chatgpt.com/images"
LOGIN_URL = "https://chatgpt.com/auth/login"

CREATE_BTN_SELECTORS = [
    'button:has-text("Create")', 'button:has-text("New image")',
    'button:has-text("New")', 'a:has-text("Create")',
    '[data-testid="create-button"]', 'button[aria-label*="Create"]',
    'button:has(svg.lucide-plus)',
]

GENERATE_BTN_SELECTORS = [
    '[data-testid="send-button"]', 'button[type="submit"]',
    'button:has(svg.lucide-arrow-up)', 'button[aria-label*="Send"]',
    'button:has-text("Generate")', 'button:has-text("Send")',
]

IMAGE_SELECTORS = [
    'img[src*="dalle"]', 'img[src*="oaidalle"]',
    'img[src*="gpt-image"]', 'img[alt*="DALL"]', 'img[alt*="Generated"]',
]

STOP_SELECTORS = [
    '[data-testid="stop-button"]', 'button:has(svg.lucide-square)',
    'button[aria-label="Stop"]', 'button:has-text("Stop")',
]

POPUP_SELECTORS = [
    'button:has-text("Okay, let\'s go")', 'button:has-text("Got it")',
    'button:has-text("Stay logged out")', 'button:has-text("Continue")',
    'button:has-text("Dismiss")', 'button:has-text("Okay")',
    '[aria-label="Close"]', '.btn-close',
]

PROMPT_SELECTORS = [
    '#prompt-textarea', 'textarea', '[contenteditable="true"]',
    'div[contenteditable="true"]', '[data-message-author-role]',
]


async def launch_browser():
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=not os.getenv("DEBUG", "false").lower() == "true",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox", "--disable-setuid-sandbox",
            "--disable-dev-shm-usage", "--disable-gpu",
            "--single-process", "--disable-accelerated-2d-canvas",
            "--no-first-run",
        ]
    )
    return p, browser


async def create_context(browser):
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        locale="en-US",
    )
    return ctx


def fix_samesite(cookies):
    same_site_map = {"strict": "Strict", "lax": "Lax", "none": "None"}
    for c in cookies:
        ss = c.get("sameSite", "")
        if isinstance(ss, str) and ss.lower() in same_site_map:
            c["sameSite"] = same_site_map[ss.lower()]
        if c.get("sameSite") not in ("Strict", "Lax", "None"):
            c.pop("sameSite", None)
    return cookies


async def dismiss_popups(page):
    for sel in POPUP_SELECTORS:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(1)
        except:
            pass


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


async def capture_profile_name(p):
    NAME_SELECTORS = [
        '[data-testid="user-avatar"] img[alt]', '[data-testid="profile-name"]',
        'nav button span.truncate', 'nav button div.truncate',
        '[data-testid="user-menu"] span', 'header button span.truncate',
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


def display_name(account):
    return account.get("profile_name") or account.get("label", "Account")


async def login(account, cb=None):
    label = account.get("label", "?")
    print(f"[worker] ========== LOGIN START: {label} ==========")

    cookies = account.get("cookies", [])
    print(f"[worker] Found {len(cookies)} cookies in account data")
    if not cookies:
        print(f"[worker] FAILED - No cookies in account")
        return None, None, None

    # Step 1: Launch browser
    print(f"[worker] Step 1: Launching Chromium...")
    p, browser = await launch_browser()
    print(f"[worker] Step 1: DONE - Browser launched")

    # Step 2: Create context + page
    print(f"[worker] Step 2: Creating context + page (no cookies yet)...")
    ctx = await create_context(browser)
    page = await ctx.new_page()
    await stealth_async(page)
    print(f"[worker] Step 2: DONE - Page created")

    # Step 3: Wait 5 seconds
    print(f"[worker] Step 3: Waiting 5 seconds (no cookies)...")
    await asyncio.sleep(5)
    print(f"[worker] Step 3: DONE - 5 seconds complete")

    # Step 4: Navigate to chatgpt.com (no cookies)
    print(f"[worker] Step 4: Navigating to {CHATGPT_URL} (NO cookies)...")
    try:
        await page.goto(CHATGPT_URL, wait_until="networkidle", timeout=45000)
        print(f"[worker] Step 4: DONE - URL: {page.url}")
    except Exception as e:
        print(f"[worker] Step 4: Navigation error - {e}")
        await browser.close()
        return None, None, None

    await asyncio.sleep(3)

    # Step 5: Reload page
    print(f"[worker] Step 5: Reloading page...")
    try:
        await page.reload(wait_until="networkidle", timeout=30000)
        print(f"[worker] Step 5: DONE - Page reloaded")
    except Exception as e:
        print(f"[worker] Step 5: Reload error - {e}")
        await browser.close()
        return None, None, None

    # Step 6: Inject cookies NOW (after page load + reload)
    print(f"[worker] Step 6: Injecting {len(cookies)} cookies...")
    cookies = fix_samesite(cookies)
    await ctx.add_cookies(cookies)
    print(f"[worker] Step 6: DONE - Cookies injected")
    await asyncio.sleep(3)

    # Step 7: Go to chatgpt.com again (WITH cookies)
    print(f"[worker] Step 7: Navigating to {CHATGPT_URL} (WITH cookies)...")
    try:
        await page.goto(CHATGPT_URL, wait_until="networkidle", timeout=45000)
        print(f"[worker] Step 7: DONE - URL: {page.url}")
    except Exception as e:
        print(f"[worker] Step 7: Navigation error - {e}")
        await browser.close()
        return None, None, None

    await asyncio.sleep(5)

    # Step 8: Check login status
    print(f"[worker] Step 8: Checking login status...")
    if LOGIN_URL in page.url:
        print(f"[worker] Step 8: FAILED - Session expired (redirected to login)")
        mark_expired(account["_id"])
        await browser.close()
        return None, None, None
    print(f"[worker] Step 8: DONE - Login verified")

    # Step 9: Dismiss popups
    print(f"[worker] Step 9: Dismissing popups...")
    await dismiss_popups(page)
    await asyncio.sleep(2)
    print(f"[worker] Step 9: DONE")

    # Step 10: Navigate to /images
    print(f"[worker] Step 10: Navigating to {IMAGES_URL}...")
    if cb:
        await cb("📍 Opening Images page...")
    try:
        await page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"[worker] Step 10: Navigation error (non-fatal): {e}")
    await asyncio.sleep(5)
    print(f"[worker] Step 10: DONE - URL: {page.url}")

    # Capture profile name
    name = await capture_profile_name(page)
    if name:
        update_profile_name(account["_id"], name)
        print(f"[worker] Profile name: {name}")

    print(f"[worker] ========== LOGIN COMPLETE: {label} ==========")
    return page, ctx, browser


async def ensure_prompt_visible(p):
    body = await p.text_content("body") or ""
    if LOGIN_URL in p.url:
        return False

    for sel in PROMPT_SELECTORS:
        try:
            el = await p.wait_for_selector(sel, timeout=5000)
            if el and await el.is_visible():
                return True
        except:
            pass

    for btn_sel in CREATE_BTN_SELECTORS:
        try:
            btn = await p.query_selector(btn_sel)
            if btn and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(3)
                for sel in PROMPT_SELECTORS:
                    try:
                        el = await p.wait_for_selector(sel, timeout=5000)
                        if el and await el.is_visible():
                            return True
                    except:
                        pass
        except:
            pass

    return False


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


async def submit_prompt(prompt, image_size="1:1", retry=5, progress_callback=None):
  async with worker_lock:
    print(f"[worker] submit_prompt called: '{prompt[:50]}...' size={image_size} retry={retry}")
    for attempt in range(retry):
        account = get_next_account()
        if not account:
            print("[worker] NO ACCOUNTS available")
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

        p, ctx, browser = await login(account, cb=progress_callback)
        if p is None:
            mark_error(account["_id"])
            if progress_callback:
                await progress_callback(f"⚠️ `{name}` login failed — skipping")
            continue

        if progress_callback:
            await progress_callback(f"✅ Logged in as `{name}`")

        print(f"[worker] URL before prompt: {p.url}")
        await dismiss_popups(p)

        if not await ensure_prompt_visible(p):
            print(f"[worker] ERROR: Prompt not visible")
            await browser.close()
            mark_error(account["_id"])
            if progress_callback:
                await progress_callback("⚠️ No prompt input found, rotating...")
            continue

        try:
            ta = await find_visible(p, PROMPT_SELECTORS, timeout=5000)
            if not ta:
                raise Exception("Prompt not found")

            await ta.click(click_count=3)
            await asyncio.sleep(0.3)
            await p.keyboard.type(prompt, delay=10)
            await asyncio.sleep(1)

            send_btn = await find_visible(p, GENERATE_BTN_SELECTORS, timeout=5000)
            if send_btn:
                await send_btn.click()
                print("[worker] Clicked send button")
            else:
                await p.keyboard.press("Enter")
                print("[worker] Pressed Enter")

            await asyncio.sleep(3)

            if progress_callback:
                await progress_callback(f"⏳ Generating image...")

            image_url = await wait_for_image(p)

            if image_url:
                mark_success(account["_id"])
                print(f"[worker] IMAGE GENERATED: {image_url[:80]}...")
                await browser.close()
                if progress_callback:
                    await progress_callback(f"✅ Done on `{name}`")
                return {"success": True, "image_url": image_url, "account": name}

            body = await p.text_content("body") or ""
            print(f"[worker] No image found. Body snippet: {body[:200]}")

            reset_at = parse_limit_reset_time(body)
            if reset_at:
                mark_limited(account["_id"], reset_at)
                await browser.close()
                left = (reset_at - datetime.now(timezone.utc)).total_seconds()
                h = int(left // 3600)
                m = int((left % 3600) // 60)
                if progress_callback:
                    await progress_callback(f"⏳ `{name}` limit — resets in {h}h {m}m")
                continue

            await browser.close()
            if progress_callback:
                await progress_callback("❌ No image generated")
            return {"success": False, "error": "No image generated"}

        except Exception as e:
            mark_error(account["_id"])
            try:
                await browser.close()
            except:
                pass
            if progress_callback:
                await progress_callback(f"⚠️ {str(e)[:60]}... rotating")
            continue

    return {"success": False, "error": "All accounts exhausted"}


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

            p, ctx, browser = await login(account, cb=progress_callback)
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
                    await dismiss_popups(p)

                    if not await ensure_prompt_visible(p):
                        results.append({"success": False, "error": "Prompt input not found"})
                        continue

                    ta = await find_visible(p, PROMPT_SELECTORS, timeout=5000)
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
                        await p.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(2)

                except Exception as e:
                    results.append({"success": False, "error": str(e)[:60]})

            await browser.close()
            return results

        return [{"success": False, "error": "All accounts exhausted"} for _ in prompts]


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

        p, browser = None, None
        try:
            pp, browser = await launch_browser()
            ctx = await create_context(browser)
            page = await ctx.new_page()
            await stealth_async(page)

            cookies = fix_samesite(d.get("cookies", []))
            await ctx.add_cookies(cookies)

            await page.goto(CHATGPT_URL, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(5)
            await dismiss_popups(page)

            if LOGIN_URL in page.url:
                print(f"[worker] check_session: {label} EXPIRED")
                name = d.get("profile_name") or label
                expired.append({"label": label, "profile_name": name, "deleted": True})
                accounts_col.delete_one({"_id": d["_id"]})
            else:
                print(f"[worker] check_session: {label} OK")

            await browser.close()
        except Exception as e:
            print(f"[worker] check_session: {label} ERROR — {e}")
            if browser:
                try:
                    await browser.close()
                except:
                    pass

    print(f"[worker] check_session done: {len(expired)} expired/deleted")
    return expired
