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
_browsers_lock = asyncio.Lock()
_browsers = {}

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

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox", "--disable-setuid-sandbox",
    "--disable-dev-shm-usage", "--disable-gpu",
    "--single-process", "--disable-accelerated-2d-canvas",
    "--no-first-run",
]


async def _launch_browser():
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=not os.getenv("DEBUG", "false").lower() == "true",
        args=BROWSER_ARGS,
    )
    return p, browser


async def _new_context(browser):
    return await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=USER_AGENT,
        locale="en-US",
    )


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


# ── Persistent browser pool ──

async def _login_account(account, cb=None):
    """Full 10-step login for an account. Returns BrowserSession."""
    label = account.get("label", "?")
    print(f"[worker] ========== PERSISTENT LOGIN: {label} ==========")

    cookies = account.get("cookies", [])
    if not cookies:
        print(f"[worker] FAILED - No cookies for {label}")
        return None

    p, browser = await _launch_browser()
    ctx = await _new_context(browser)
    page = await ctx.new_page()
    await stealth_async(page)

    # Step 3: Wait 5s
    await asyncio.sleep(5)

    # Step 4: Navigate (no cookies)
    try:
        await page.goto(CHATGPT_URL, wait_until="networkidle", timeout=45000)
    except Exception as e:
        print(f"[worker] Step 4 error: {e}")
        await browser.close()
        return None
    await asyncio.sleep(3)

    # Step 5: Reload
    try:
        await page.reload(wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"[worker] Step 5 error: {e}")
        await browser.close()
        return None

    # Step 6: Inject cookies
    cookies = fix_samesite(cookies)
    await ctx.add_cookies(cookies)
    await asyncio.sleep(3)

    # Step 7: Navigate WITH cookies
    try:
        await page.goto(CHATGPT_URL, wait_until="networkidle", timeout=45000)
    except Exception as e:
        print(f"[worker] Step 7 error: {e}")
        await browser.close()
        return None
    await asyncio.sleep(5)

    # Step 8: Check login
    if LOGIN_URL in page.url:
        print(f"[worker] Login FAILED - {label} expired")
        mark_expired(account["_id"])
        await browser.close()
        return None
    print(f"[worker] Login verified for {label}")

    # Step 9: Dismiss popups
    await dismiss_popups(page)
    await asyncio.sleep(2)

    # Step 10: Navigate to /images
    if cb:
        await cb("📍 Opening Images page...")
    try:
        await page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"[worker] Step 10 nav error (non-fatal): {e}")
    await asyncio.sleep(5)

    name = await capture_profile_name(page)
    if name:
        update_profile_name(account["_id"], name)
        print(f"[worker] Profile name: {name}")

    storage = await ctx.storage_state()

    print(f"[worker] ========== PERSISTENT LOGIN DONE: {label} ==========")
    return {
        "playwright": p,
        "browser": browser,
        "master_ctx": ctx,
        "master_page": page,
        "storage_state": storage,
        "account_id": account["_id"],
        "label": label,
        "last_refreshed": datetime.now(timezone.utc),
    }


async def get_or_init_browser(account):
    """Get persistent browser session for account, init if missing."""
    aid = account["_id"]
    async with _browsers_lock:
        existing = _browsers.get(aid)
        if existing:
            if existing["browser"] and existing["browser"].is_connected():
                return existing
            print(f"[worker] Browser {existing['label']} disconnected, re-init...")
            try:
                await existing["browser"].close()
            except:
                pass
        new_session = await _login_account(account)
        if new_session:
            _browsers[aid] = new_session
        return new_session


async def _create_guest_context(browser_session):
    """Create a fresh isolated context from saved storage_state."""
    storage = browser_session.get("storage_state")
    ctx = await browser_session["browser"].new_context(
        storage_state=storage,
        viewport={"width": 1280, "height": 800},
        user_agent=USER_AGENT,
        locale="en-US",
    )
    page = await ctx.new_page()
    await stealth_async(page)
    return ctx, page


def _is_expired(page_url):
    return LOGIN_URL in page_url


async def _refresh_storage(browser_session):
    """Update storage_state from master context."""
    try:
        s = await browser_session["master_ctx"].storage_state()
        browser_session["storage_state"] = s
        browser_session["last_refreshed"] = datetime.now(timezone.utc)
    except Exception as e:
        print(f"[worker] storage refresh error for {browser_session['label']}: {e}")


# ── Public API ──

async def init_all_browsers_background():
    """Startup: init browsers for all non-expired accounts in background."""
    accounts = Account.get_all()
    print(f"[worker] Initializing {len(accounts)} persistent browsers...")
    for acct in accounts:
        if acct.get("expired") or acct.get("limited"):
            continue
        aid = acct["_id"]
        async with _browsers_lock:
            if aid in _browsers:
                continue
        asyncio.create_task(get_or_init_browser(acct))
    print(f"[worker] Browser init background tasks launched")


async def submit_prompt(prompt, image_size="1:1", retry=5, progress_callback=None):
    async with worker_lock:
        print(f"[worker] submit_prompt: '{prompt[:50]}...' size={image_size}")
        for attempt in range(retry):
            account = get_next_account()
            if not account:
                if progress_callback:
                    await progress_callback("❌ No valid accounts available")
                return {"success": False, "error": "No valid accounts"}

            if account.get("_limited_info"):
                limited_accts = account["accounts"]
                acct_names = ", ".join([a["label"] for a in limited_accts])
                first = limited_accts[0]
                h, m = first["hours_left"], first["minutes_left"]
                err = f"⏳ Account limit reached — resets in {h}h {m}m"
                print(f"[worker] ALL LIMITED: {err}")
                if progress_callback:
                    await progress_callback(f"{err} ({acct_names})")
                return {"success": False, "error": err, "limited_accounts": limited_accts}

            name = display_name(account)
            if progress_callback:
                await progress_callback(f"🔄 Attempt {attempt+1} — `{name}`")

            session = await get_or_init_browser(account)
            if not session:
                mark_error(account["_id"])
                if progress_callback:
                    await progress_callback(f"⚠️ `{name}` login failed — skipping")
                continue

            if progress_callback:
                await progress_callback(f"✅ Logged in as `{name}`")

            ctx, page = None, None
            try:
                ctx, page = await _create_guest_context(session)
                await page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
                await dismiss_popups(page)

                if not await ensure_prompt_visible(page):
                    print(f"[worker] Prompt not visible for {name}")
                    await ctx.close()
                    mark_error(account["_id"])
                    if progress_callback:
                        await progress_callback("⚠️ No prompt input, rotating...")
                    continue

                ta = await find_visible(page, PROMPT_SELECTORS, timeout=5000)
                if not ta:
                    await ctx.close()
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

                if progress_callback:
                    await progress_callback("⏳ Generating image...")

                image_url = await wait_for_image(page)

                if image_url:
                    mark_success(account["_id"])
                    print(f"[worker] IMAGE: {image_url[:80]}...")
                    await ctx.close()
                    if progress_callback:
                        await progress_callback(f"✅ Done on `{name}`")
                    await _refresh_storage(session)
                    return {"success": True, "image_url": image_url, "account": name}

                body = await page.text_content("body") or ""
                reset_at = parse_limit_reset_time(body)
                if reset_at:
                    mark_limited(account["_id"], reset_at)
                    await ctx.close()
                    left = (reset_at - datetime.now(timezone.utc)).total_seconds()
                    h, m = int(left // 3600), int((left % 3600) // 60)
                    if progress_callback:
                        await progress_callback(f"⏳ `{name}` limit — resets in {h}h {m}m")
                    continue

                await ctx.close()
                if progress_callback:
                    await progress_callback("❌ No image generated")
                return {"success": False, "error": "No image generated"}

            except Exception as e:
                mark_error(account["_id"])
                if ctx:
                    try:
                        await ctx.close()
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

            session = await get_or_init_browser(account)
            if not session:
                mark_error(account["_id"])
                continue

            if progress_callback:
                await progress_callback(f"✅ Logged in as `{name}`")

            ctx, page = None, None
            try:
                ctx, page = await _create_guest_context(session)
                results = []
                for i, prompt in enumerate(prompts):
                    if progress_callback:
                        await progress_callback(f"📝 `{i+1}/{len(prompts)}`: `{prompt[:40]}...`")

                    try:
                        await dismiss_popups(page)

                        if not await ensure_prompt_visible(page):
                            results.append({"success": False, "error": "Prompt input not found"})
                            continue

                        ta = await find_visible(page, PROMPT_SELECTORS, timeout=5000)
                        if not ta:
                            results.append({"success": False, "error": "Prompt input not found"})
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
                        else:
                            results.append({"success": False, "error": "No image"})

                        if i < len(prompts) - 1:
                            await page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
                            await asyncio.sleep(2)

                    except Exception as e:
                        results.append({"success": False, "error": str(e)[:60]})

                return results
            finally:
                if ctx:
                    try:
                        await ctx.close()
                    except:
                        pass
                await _refresh_storage(session)

        return [{"success": False, "error": "All accounts exhausted"} for _ in prompts]


async def check_session():
    """Check all accounts using their persistent browser master context."""
    async with _browsers_lock:
        docs = Account.get_all()
        print(f"[worker] check_session: {len(docs)} accounts")
        expired = []
        for d in docs:
            label = d.get("label", "?")
            if d.get("expired"):
                name = d.get("profile_name") or label
                expired.append({"label": label, "profile_name": name, "deleted": True})
                accounts_col.delete_one({"_id": d["_id"]})
                if d["_id"] in _browsers:
                    try:
                        await _browsers[d["_id"]]["browser"].close()
                    except:
                        pass
                    del _browsers[d["_id"]]
                continue

            aid = d["_id"]
            session = _browsers.get(aid)
            if not session:
                print(f"[worker] check_session: {label} no persistent browser, launching temp check...")
                try:
                    p, browser = await _launch_browser()
                    ctx = await _new_context(browser)
                    page = await ctx.new_page()
                    await stealth_async(page)
                    cookies = fix_samesite(d.get("cookies", []))
                    await ctx.add_cookies(cookies)
                    await page.goto(CHATGPT_URL, wait_until="networkidle", timeout=45000)
                    await asyncio.sleep(5)
                    if LOGIN_URL in page.url:
                        name = d.get("profile_name") or label
                        expired.append({"label": label, "profile_name": name, "deleted": True})
                        accounts_col.delete_one({"_id": d["_id"]})
                    await browser.close()
                except Exception as e:
                    print(f"[worker] check_session: {label} temp error — {e}")
                    if browser:
                        try:
                            await browser.close()
                        except:
                            pass
                continue

            try:
                page = await session["master_ctx"].new_page()
                await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
                if LOGIN_URL in page.url:
                    print(f"[worker] check_session: {label} EXPIRED via persistent browser")
                    name = d.get("profile_name") or label
                    expired.append({"label": label, "profile_name": name, "deleted": True})
                    accounts_col.delete_one({"_id": d["_id"]})
                    try:
                        await session["browser"].close()
                    except:
                        pass
                    del _browsers[aid]
                else:
                    print(f"[worker] check_session: {label} OK")
                    _refresh_storage(session)
                await page.close()
            except Exception as e:
                print(f"[worker] check_session: {label} error — {e}")
                try:
                    await session["browser"].close()
                except:
                    pass
                del _browsers[aid]

        print(f"[worker] check_session done: {len(expired)} expired")
        return expired
