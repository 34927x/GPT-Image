import asyncio, re, os, io
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

# Single persistent browser (lazy init, kept alive across requests)
_browser_data = {"p": None, "browser": None}

# Current logged-in account's master context
_master = {"ctx": None, "page": None, "account": None, "storage_state": None}

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


def _sanitize_cookies(cookies):
    """Convert Chrome extension cookie format to Playwright-compatible format."""
    same_site_map = {"strict": "Strict", "lax": "Lax", "none": "None", "no_restriction": "None", "unspecified": "None"}
    allowed = {"name", "value", "domain", "path", "httpOnly", "secure", "sameSite", "expires", "maxAge"}
    out = []
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        if not name or not value:
            continue
        cleaned = {"name": str(name), "value": str(value)}
        if "domain" in c and c["domain"]:
            cleaned["domain"] = str(c["domain"])
        if "path" in c and c["path"]:
            cleaned["path"] = str(c["path"])
        if "httpOnly" in c:
            cleaned["httpOnly"] = bool(c["httpOnly"])
        if "secure" in c:
            cleaned["secure"] = bool(c["secure"])
        ss = c.get("sameSite", "")
        if isinstance(ss, str) and ss.lower() in same_site_map:
            cleaned["sameSite"] = same_site_map[ss.lower()]
        exp = c.get("expirationDate") or c.get("expires")
        if exp and isinstance(exp, (int, float)):
            cleaned["expires"] = exp
        out.append(cleaned)
    return out


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


# ── Browser lifecycle (single persistent browser) ──

def get_browser():
    return _browser_data["browser"]

def get_playwright():
    return _browser_data["p"]

async def ensure_browser():
    if get_browser() and get_browser().is_connected():
        return get_browser()
    if get_browser():
        try:
            await get_browser().close()
        except:
            pass
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=not os.getenv("DEBUG", "false").lower() == "true",
        args=BROWSER_ARGS,
    )
    _browser_data["p"] = p
    _browser_data["browser"] = browser
    print("[worker] Single persistent browser launched")
    return browser


async def close_browser():
    if get_browser():
        try:
            await get_browser().close()
        except:
            pass
    if get_playwright():
        try:
            await get_playwright().stop()
        except:
            pass
    _browser_data["p"] = None
    _browser_data["browser"] = None
    _master["ctx"] = None
    _master["page"] = None
    _master["account"] = None
    _master["storage_state"] = None


# ── Master context (logged-in session per account) ──

async def login_account(account, cb=None):
    """
    Exact test_playwright.py flow:
    1. Launch browser (or reuse)
    2. Create context + page (NO cookies)
    3. Wait 5s
    4. Navigate to chatgpt.com
    5. Reload
    6. Inject cookies (sameSite fix)
    7. Navigate WITH cookies
    8. Check login
    9. Dismiss popups
    10. Navigate to /images
    """
    label = account.get("label", "?")
    print(f"[worker] ===== LOGIN: {label} (test_playwright.py flow) =====")

    cookies = account.get("cookies", [])
    if not cookies:
        print(f"[worker] No cookies for {label}, deleting")
        mark_expired(account["_id"])
        return False
    if len(cookies) < 10:
        print(f"[worker] Only {len(cookies)} cookies for {label} (need >= 10), deleting")
        mark_expired(account["_id"])
        return False

    browser = await ensure_browser()

    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=USER_AGENT,
        locale="en-US",
    )
    page = await ctx.new_page()
    await stealth_async(page)

    if cb:
        await cb("🔄 Launching browser...")

    await asyncio.sleep(5)

    if cb:
        await cb("🌐 Navigating to ChatGPT...")
    try:
        await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"[worker] Step 4 nav error: {e}")
        await ctx.close()
        return False
    await asyncio.sleep(3)

    try:
        await page.reload(wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"[worker] Step 5 reload error: {e}")
        await ctx.close()
        return False

    if cb:
        await cb("🍪 Injecting cookies...")
    cookies = _sanitize_cookies(cookies)
    print(f"[worker] {len(cookies)} valid cookies after sanitize")
    try:
        await ctx.add_cookies(cookies)
    except Exception as e:
        print(f"[worker] Step 6 add_cookies error: {e}")
        await ctx.close()
        return False
    await asyncio.sleep(3)

    if cb:
        await cb("🔄 Verifying login...")
    try:
        await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"[worker] Step 7 nav error: {e}")
        await ctx.close()
        return False
    await asyncio.sleep(5)

    if LOGIN_URL in page.url:
        print(f"[worker] LOGIN FAILED: {label} expired")
        mark_expired(account["_id"])
        await ctx.close()
        if cb:
            await cb("❌ Session expired — account removed")
        return False
    print(f"[worker] Login verified for {label}")

    await dismiss_popups(page)
    await asyncio.sleep(2)

    if cb:
        await cb("📍 Opening Images page...")
    try:
        await page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"[worker] Images nav error: {e}")
    await asyncio.sleep(5)

    name = await capture_profile_name(page)
    if name:
        update_profile_name(account["_id"], name)

    storage = await ctx.storage_state()

    # Close old master if switching accounts
    if _master["ctx"] and _master["ctx"] != ctx:
        try:
            await _master["ctx"].close()
        except:
            pass

    _master["ctx"] = ctx
    _master["page"] = page
    _master["account"] = account
    _master["storage_state"] = storage

    print(f"[worker] ===== LOGIN DONE: {label} =====")
    return True


async def ensure_logged_in(account, cb=None):
    """Make sure master context is logged into the given account."""
    current_id = _master["account"]["_id"] if _master["account"] else None
    if current_id == account["_id"]:
        return True
    return await login_account(account, cb=cb)


async def create_guest_context():
    """Fresh isolated context from master's storage_state (guest profile)."""
    if not _master["storage_state"]:
        return None, None
    browser = get_browser()
    if not browser:
        return None, None
    ctx = await browser.new_context(
        storage_state=_master["storage_state"],
        viewport={"width": 1280, "height": 800},
        user_agent=USER_AGENT,
        locale="en-US",
    )
    page = await ctx.new_page()
    await stealth_async(page)
    return ctx, page


# ── Submit prompt ──

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
                limited = account["accounts"]
                names = ", ".join([a["label"] for a in limited])
                first = limited[0]
                h, m = first["hours_left"], first["minutes_left"]
                err = f"⏳ All accounts limited — resets in {h}h {m}m"
                print(f"[worker] {err}")
                if progress_callback:
                    await progress_callback(f"{err} ({names})")
                return {"success": False, "error": err, "limited_accounts": limited}

            name = display_name(account)
            if progress_callback:
                await progress_callback(f"🔄 Attempt {attempt+1} — `{name}`")

            logged_in = await ensure_logged_in(account, cb=progress_callback)
            if not logged_in:
                mark_error(account["_id"])
                if progress_callback:
                    await progress_callback(f"⚠️ `{name}` login failed")
                continue

            if progress_callback:
                await progress_callback(f"✅ Logged in as `{name}`")

            ctx, page = None, None
            try:
                ctx, page = await create_guest_context()
                if not ctx:
                    if progress_callback:
                        await progress_callback("⚠️ Failed to create guest context")
                    continue

                await page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
                await dismiss_popups(page)

                if not await ensure_prompt_visible(page):
                    print(f"[worker] Prompt not visible for {name}")
                    await ctx.close()
                    mark_error(account["_id"])
                    if progress_callback:
                        await progress_callback("⚠️ Prompt input not found")
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
                    await progress_callback(f"⚠️ {str(e)[:60]}")
                continue

        return {"success": False, "error": "All accounts exhausted"}


# ── Submit bulk ──

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

            logged_in = await ensure_logged_in(account, cb=progress_callback)
            if not logged_in:
                mark_error(account["_id"])
                continue

            if progress_callback:
                await progress_callback(f"✅ Logged in as `{name}`")

            ctx, page = None, None
            try:
                ctx, page = await create_guest_context()
                if not ctx:
                    continue

                results = []
                limit_hit = False
                for i, prompt in enumerate(prompts):
                    if limit_hit:
                        break

                    if progress_callback:
                        await progress_callback(f"📝 `{i+1}/{len(prompts)}`: `{prompt[:40]}...`")

                    try:
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
                        else:
                            body = await page.text_content("body") or ""
                            reset_at = parse_limit_reset_time(body)
                            if reset_at:
                                mark_limited(account["_id"], reset_at)
                                results.append({"success": False, "error": "Limit reached"})
                                limit_hit = True
                            else:
                                results.append({"success": False, "error": "No image"})

                        if i < len(prompts) - 1 and not limit_hit:
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

        return [{"success": False, "error": "All accounts exhausted"} for _ in prompts]


# ── Session check ──

async def check_session():
    docs = Account.get_all()
    print(f"[worker] check_session: {len(docs)} accounts")
    expired = []
    for d in docs:
        label = d.get("label", "?")
        if d.get("expired"):
            name = d.get("profile_name") or label
            expired.append({"label": label, "profile_name": name, "deleted": True})
            accounts_col.delete_one({"_id": d["_id"]})
            continue

        aid = d["_id"]
        is_current = _master["account"] and _master["account"]["_id"] == aid

        if is_current and _master["page"]:
            try:
                page = await _master["ctx"].new_page()
                await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
                if LOGIN_URL in page.url:
                    print(f"[worker] check_session: {label} EXPIRED")
                    name = d.get("profile_name") or label
                    expired.append({"label": label, "profile_name": name, "deleted": True})
                    accounts_col.delete_one({"_id": d["_id"]})
                    await close_browser()
                else:
                    print(f"[worker] check_session: {label} OK")
                    storage = await _master["ctx"].storage_state()
                    _master["storage_state"] = storage
                await page.close()
                continue
            except Exception as e:
                print(f"[worker] check_session: {label} error — {e}")
                await close_browser()

        # Not current account — use persistent browser (new context)
        try:
            browser = get_browser()
            if not browser or not browser.is_connected():
                print(f"[worker] check_session: {label} persistent browser unavailable")
                continue
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=USER_AGENT,
            )
            page = None
            try:
                page = await ctx.new_page()
                await stealth_async(page)
                await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
                cookies = _sanitize_cookies(d.get("cookies", []))
                try:
                    await ctx.add_cookies(cookies)
                except Exception as ce:
                    print(f"[worker] check_session: {label} add_cookies error: {ce}")
                    await ctx.close()
                    continue
                await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(5)
                if LOGIN_URL in page.url:
                    name = d.get("profile_name") or label
                    expired.append({"label": label, "profile_name": name, "deleted": True})
                    accounts_col.delete_one({"_id": d["_id"]})
            finally:
                if page:
                    try:
                        await page.close()
                    except:
                        pass
                try:
                    await ctx.close()
                except:
                    pass
        except Exception as e:
            print(f"[worker] check_session: {label} temp error — {e}")

    print(f"[worker] check_session done: {len(expired)} expired")
    return expired


# ── Background init (lazy — just ensures browser is ready) ──

async def init_browser_background():
    """Lazy init: just make sure the persistent browser process exists."""
    try:
        await ensure_browser()
        print("[worker] Background browser init complete")
    except Exception as e:
        print(f"[worker] Background browser init error: {e}")
