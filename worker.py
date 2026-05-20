import asyncio, re, os, io, sys, json
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright, TimeoutError as PwTimeout
from playwright_stealth import stealth_async

import config
from config import Account, accounts_col, queue_col, db

# --- HELPERS ---

def sanitize_filename(name):
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '-', name)
    return name.strip('-').lower()[:50]

def make_image_filename(prompt, index=0):
    num = str(index).zfill(3)
    words = re.sub(r'[^a-zA-Z0-9\s]', '', prompt).split()
    slug = '-'.join(words[:4]).lower()
    return f"{num}-{slug}-By_@TurabCoder.png"

def now_iso():
    return datetime.now(timezone.utc).isoformat()


# --- ACCOUNT MANAGER ---





def is_admin(user_id):
    import config
    return user_id in config.ADMIN_IDS

def export_accounts():
    docs = Account.get_all()
    data = []
    for d in docs:
        data.append({
            "label": d["label"],
            "cookies": d["cookies"],
            "created_at": d["created_at"].isoformat() if d.get("created_at") else None
        })
    return data

def import_accounts(data):
    count = 0
    for item in data:
        if not item.get("cookies"):
            continue
        label = item.get("label", f"Imported-{count}")
        exists = accounts_col.find_one({"label": label})
        if exists:
            label = f"{label}-{count}"
        Account.create(label, item["cookies"])
        count += 1
    return count

def get_next_account():
    now = datetime.now(timezone.utc)
    docs = list(accounts_col.find().sort("last_used", 1))
    limited_accounts = []
    for d in docs:
        if d.get("expired"):
            continue
        if d.get("limited"):
            reset_at = d.get("limit_reset_at")
            if reset_at and reset_at > now:
                left = (reset_at - now).total_seconds()
                h = int(left // 3600)
                m = int((left % 3600) // 60)
                limited_accounts.append({
                    "label": d.get("profile_name") or d.get("label", "Unknown"),
                    "reset_at": reset_at,
                    "hours_left": h,
                    "minutes_left": m
                })
                continue
            accounts_col.update_one({"_id": d["_id"]}, {"$set": {"limited": False, "limit_reset_at": None, "limit_hit_at": None, "error_count": 0}})
        errs = d.get("error_count", 0)
        if errs < 3:
            return d
    if limited_accounts:
        return {"_limited_info": True, "accounts": limited_accounts}
    accounts_col.update_many({}, {"$set": {"error_count": 0}})
    return None

def mark_error(account_id):
    accounts_col.update_one({"_id": account_id}, {"$inc": {"error_count": 1}})

def mark_success(account_id):
    accounts_col.update_one({"_id": account_id}, {
        "$set": {"last_used": datetime.now(timezone.utc), "error_count": 0}
    })

def mark_expired(account_id):
    doc = accounts_col.find_one({"_id": account_id})
    if doc:
        name = doc.get("profile_name") or doc.get("label", "Unknown")
        accounts_col.delete_one({"_id": account_id})
        return name
    return None

def mark_limited(account_id, reset_at):
    accounts_col.update_one({"_id": account_id}, {
        "$set": {
            "limited": True,
            "limit_reset_at": reset_at,
            "limit_hit_at": datetime.now(timezone.utc),
            "last_used": datetime.now(timezone.utc)
        }
    })

def update_profile_name(account_id, name):
    if name:
        accounts_col.update_one({"_id": account_id}, {"$set": {"profile_name": name}})

def reset_limited_accounts():
    now = datetime.now(timezone.utc)
    count = accounts_col.update_many(
        {"limited": True, "limit_reset_at": {"$lt": now}},
        {"$set": {"limited": False, "limit_reset_at": None, "limit_hit_at": None, "error_count": 0}}
    )
    return count.modified_count

def get_expired_accounts():
    return list(accounts_col.find({"expired": True}))

def add_manual_account(cookies, label=None):
    if isinstance(cookies, str):
        cookies = json.loads(cookies)
    if not isinstance(cookies, list) or not cookies:
        return False, "Invalid cookies format"
    label = label or f"manual-{len(list(accounts_col.find()))+1}"
    account = accounts_col.find_one({"label": label})
    if account:
        accounts_col.update_one(
            {"_id": account["_id"]},
            {"$set": {"cookies": cookies, "source": "manual", "expired": False, "error_count": 0}}
        )
        return True, f"Updated: {label}"
    Account.create(label, cookies, source="manual")
    return True, f"Created: {label}"

def get_session_status():
    docs = Account.get_all()
    now = datetime.now(timezone.utc)
    lines = []
    for i, d in enumerate(docs):
        name = d.get("profile_name") or d.get("label", f"#{i+1}")
        last = d.get("last_used") or d.get("created_at")
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        expired = d.get("expired", False)
        limited = d.get("limited", False)
        errs = d.get("error_count", 0)
        hours_since = (now - last).total_seconds() / 3600 if last else 0
        first_loaded = d.get("first_loaded_at")
        if first_loaded and first_loaded.tzinfo is None:
            first_loaded = first_loaded.replace(tzinfo=timezone.utc)
        is_fresh = first_loaded and (now - first_loaded).total_seconds() < 3600
        limit_hit_at = d.get("limit_hit_at")
        if limit_hit_at and limit_hit_at.tzinfo is None:
            limit_hit_at = limit_hit_at.replace(tzinfo=timezone.utc)
        if expired:
            status = "❌ Expired"
        elif limited:
            reset_at = d.get("limit_reset_at")
            if reset_at:
                left = (reset_at - now).total_seconds()
                h = int(left // 3600)
                m = int((left % 3600) // 60)
                status = f"⏳ Limit ({h}h {m}m left)"
            else:
                status = "⏳ Limited"
        elif errs > 0:
            status = "⚠️ Errors"
        else:
            status = "✅ Active"
        fresh_tag = " 🆕" if is_fresh else ""
        lines.append(f"{i+1}. `{name}` — {status}{fresh_tag} — {hours_since:.0f}h ago")
    return lines

def parse_limit_reset_time(body):
    m = re.search(r'resets in (?:about )?(?:(\d+)\s*hours?)?\s*(?:and\s*)?(?:(\d+)\s*minutes?)?', body.lower())
    if m:
        hours = int(m.group(1)) if m.group(1) else 0
        mins = int(m.group(2)) if m.group(2) else 0
        if hours > 0 or mins > 0:
            return datetime.now(timezone.utc) + timedelta(hours=hours, minutes=mins)
    m2 = re.search(r'(\d+)\s*hours?\s*(\d+)\s*minutes?', body.lower())
    if m2:
        return datetime.now(timezone.utc) + timedelta(hours=int(m2.group(1)), minutes=int(m2.group(2)))
    return None


# --- WORKER ---
import asyncio, re, os, io
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PwTimeout
from playwright_stealth import stealth_async


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
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-first-run",
    "--no-zygote",
    "--js-flags=--max-old-space-size=128",  # Limit JS V8 heap to 128MB
    "--disable-extensions",
    "--disable-audio-output",
    "--mute-audio",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-component-extensions-with-background-pages",
    "--disable-features=Translate,BackForwardCache,AcceptCHFrame,AvoidUnnecessaryTemplates",
    "--disable-ipc-flooding-protection",
    "--disable-renderer-backgrounding",
    "--metrics-recording-only",
]


def _sanitize_cookies(cookies):
    """Convert Chrome extension cookie format to Playwright-compatible format."""
    same_site_pw = {"strict": "Strict", "lax": "Lax", "no_restriction": "None", "unspecified": "None"}
    allowed = {"name", "value", "domain", "path", "httpOnly", "secure", "sameSite", "expires"}
    out = []
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        if not name or not value:
            continue
        cleaned = {}
        for k in allowed:
            if k in c:
                v = c[k]
                if k in ("httpOnly", "secure"):
                    cleaned[k] = bool(v)
                elif k == "sameSite":
                    ss = v.lower() if isinstance(v, str) else ""
                    if ss in same_site_pw:
                        cleaned[k] = same_site_pw[ss]
                elif k == "expires":
                    if isinstance(v, (int, float)):
                        cleaned[k] = v
                else:
                    cleaned[k] = str(v)
        if "domain" not in cleaned or not cleaned["domain"]:
            continue
        if "path" not in cleaned:
            cleaned["path"] = "/"
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


async def try_click_turnstile(p):
    try:
        for frame in p.frames:
            if "challenges.cloudflare.com" in frame.url:
                el = await frame.query_selector("input[type='checkbox']")
                if el:
                    await el.click()
                    print("[worker] Clicked Cloudflare Turnstile checkbox input")
                    return True
                el = await frame.query_selector(".mark")
                if el:
                    await el.click()
                    print("[worker] Clicked Cloudflare Turnstile mark class")
                    return True
                el = await frame.query_selector("#challenge-stage")
                if el:
                    await el.click()
                    print("[worker] Clicked Cloudflare Turnstile challenge-stage")
                    return True
    except Exception as e:
        print(f"[worker] Turnstile click attempt error: {e}")
    return False


async def wait_for_cloudflare(p, max_wait=15):
    for attempt in range(max_wait):
        title = ""
        try:
            title = await p.title()
        except:
            pass
        body = ""
        try:
            body = await p.text_content("body") or ""
        except:
            pass
        
        is_cf = ("just a moment" in title.lower() or 
                 "cloudflare" in body.lower() or 
                 "turnstile" in body.lower() or 
                 "checking your browser" in body.lower() or 
                 "verify you are human" in body.lower() or 
                 "verify is you are human" in body.lower())
        
        if not is_cf:
            return True
            
        print(f"[worker] Cloudflare challenge active (title='{title}'), waiting 1s... (attempt {attempt+1}/{max_wait})")
        await try_click_turnstile(p)
        await asyncio.sleep(1)
    return False


async def verify_login_status(page):
    await wait_for_cloudflare(page, max_wait=15)
    if LOGIN_URL in page.url:
        return False
    for sel in PROMPT_SELECTORS:
        try:
            el = await page.wait_for_selector(sel, timeout=3000)
            if el and await el.is_visible():
                return True
        except:
            pass
    try:
        login_btn = await page.query_selector('button:has-text("Log in"), a:has-text("Log in"), button:has-text("Sign up")')
        if login_btn and await login_btn.is_visible():
            return False
    except:
        pass
    if "chatgpt.com" in page.url:
        return True
    return False


async def ensure_prompt_visible(p):
    if not await verify_login_status(p):
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
            
    # Diagnostics before returning False
    title = ""
    try:
        title = await p.title()
    except:
        pass
    body = await p.text_content("body") or ""
    print(f"[worker] ensure_prompt_visible failed: url={p.url} title='{title}'")
    if "cloudflare" in body.lower() or "turnstile" in body.lower() or "checking your browser" in body.lower() or "verify you are human" in body.lower() or "verify is you are human" in body.lower():
        print("[worker] CLOUDFLARE TURNSTILE/CHALLENGE PAGE DETECTED!")
    else:
        snippet = body[:400].replace('\n', ' ').strip()
        print(f"[worker] Body snippet: {snippet}")
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
    # Browser disconnected or crashed — force-replace it
    if get_browser():
        try:
            await asyncio.wait_for(get_browser().close(), timeout=5)
        except:
            pass
        _browser_data["browser"] = None
    if get_playwright():
        try:
            await asyncio.wait_for(get_playwright().stop(), timeout=5)
        except:
            pass
        _browser_data["p"] = None
    try:
        p = await asyncio.wait_for(async_playwright().start(), timeout=10)
        browser = await asyncio.wait_for(p.chromium.launch(
            headless=not os.getenv("DEBUG", "false").lower() == "true",
            args=BROWSER_ARGS,
        ), timeout=30)
        _browser_data["p"] = p
        _browser_data["browser"] = browser
        print("[worker] Single persistent browser launched")
        return browser
    except asyncio.TimeoutError:
        print("[worker] ensure_browser timeout — giving up")
        return None
    except Exception as e:
        print(f"[worker] ensure_browser error: {e}")
        return None


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
    if not browser:
        print(f"[worker] Browser unavailable for {label}")
        return False

    try:
        ctx = await asyncio.wait_for(browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=USER_AGENT,
            locale="en-US",
        ), timeout=10)
        page = await asyncio.wait_for(ctx.new_page(), timeout=10)
    except asyncio.TimeoutError:
        print(f"[worker] Context/page creation timeout for {label}")
        return False
    except Exception as e:
        print(f"[worker] Context creation error: {e}")
        return False
    await stealth_async(page)

    if cb:
        try:
            await asyncio.wait_for(cb("🔄 Launching browser..."), timeout=5)
        except:
            pass

    await asyncio.sleep(5)
    print(f"[worker] LOGIN step4: navigating to chatgpt.com...")

    if cb:
        try:
            await asyncio.wait_for(cb("🌐 Navigating to ChatGPT..."), timeout=5)
        except:
            pass
    try:
        await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"[worker] Step 4 nav error: {e}")
        await ctx.close()
        return False
    print(f"[worker] LOGIN step4 done: url={page.url[:60]}")
    await asyncio.sleep(3)

    print(f"[worker] LOGIN step5: reloading...")
    try:
        await page.reload(wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"[worker] Step 5 reload error: {e}")
        await ctx.close()
        return False
    print(f"[worker] LOGIN step5 done")

    if cb:
        try:
            await asyncio.wait_for(cb("🍪 Injecting cookies..."), timeout=5)
        except:
            pass
    print(f"[worker] LOGIN step6: sanitizing {len(cookies)} cookies...")
    cookies = _sanitize_cookies(cookies)
    print(f"[worker] {len(cookies)} valid cookies after sanitize")
    failed = 0
    for i, c in enumerate(cookies):
        try:
            await ctx.add_cookies([c])
        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"[worker] Cookie #{i} ({c.get('name')}) failed: {str(e)[:80]}")
    if failed == len(cookies):
        print(f"[worker] ALL {failed} cookies failed — login impossible")
        await ctx.close()
        return False
    if failed:
        print(f"[worker] {failed}/{len(cookies)} cookies failed (non-critical), continuing")
    print(f"[worker] {len(cookies)-failed} cookies injected successfully")
    await asyncio.sleep(3)
    print(f"[worker] LOGIN step6 done: {len(cookies)} valid cookies, {failed} failed")

    if cb:
        try:
            await asyncio.wait_for(cb("🔄 Verifying login..."), timeout=5)
        except:
            pass
    print(f"[worker] LOGIN step7: navigating with cookies...")
    try:
        await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"[worker] Step 7 nav error: {e}")
        await ctx.close()
        return False
    print(f"[worker] LOGIN step7 done: url={page.url[:60]}")
    if not await verify_login_status(page):
        print(f"[worker] LOGIN FAILED: {label} expired or challenge failed")
        mark_expired(account["_id"])
        await ctx.close()
        if cb:
            try:
                await asyncio.wait_for(cb("❌ Session expired or invalid — account removed"), timeout=5)
            except:
                pass
        return False
    print(f"[worker] Login verified for {label}")

    await dismiss_popups(page)
    await asyncio.sleep(2)

    if cb:
        try:
            await asyncio.wait_for(cb("📍 Opening Images page..."), timeout=5)
        except:
            pass
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
    browser = get_browser()
    browser_ok = browser and browser.is_connected()
    current_id = _master["account"]["_id"] if (_master["account"] and browser_ok) else None
    if current_id == account["_id"]:
        return True
    return await login_account(account, cb=cb)


# create_guest_context removed as we use the master context directly to optimize memory usage


# ── Submit prompt ──

async def _pc(progress_callback, msg):
    """Fire progress callback with 5s timeout."""
    if progress_callback:
        try:
            await asyncio.wait_for(progress_callback(msg), timeout=5)
        except:
            pass

async def submit_prompt(prompt, image_size="1:1", retry=5, progress_callback=None):
    async with worker_lock:
        print(f"[worker] submit_prompt: '{prompt[:50]}...' size={image_size}")
        try:
            for attempt in range(retry):
                account = get_next_account()
                if not account:
                    await _pc(progress_callback, "❌ No valid accounts available")
                    return {"success": False, "error": "No valid accounts"}

                if account.get("_limited_info"):
                    limited = account["accounts"]
                    names = ", ".join([a["label"] for a in limited])
                    first = limited[0]
                    h, m = first["hours_left"], first["minutes_left"]
                    err = f"⏳ All accounts limited — resets in {h}h {m}m"
                    print(f"[worker] {err}")
                    await _pc(progress_callback, f"{err} ({names})")
                    return {"success": False, "error": err, "limited_accounts": limited}

                name = display_name(account)
                await _pc(progress_callback, f"🔄 Attempt {attempt+1} — `{name}`")

                logged_in = await ensure_logged_in(account, cb=progress_callback)
                if not logged_in:
                    mark_error(account["_id"])
                    await _pc(progress_callback, f"⚠️ `{name}` login failed")
                    continue

                await _pc(progress_callback, f"✅ Logged in as `{name}`")

                try:
                    ctx = _master["ctx"]
                    page = _master["page"]

                    await page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(3)
                    await dismiss_popups(page)

                    if not await ensure_prompt_visible(page):
                        print(f"[worker] Prompt not visible for {name}")
                        mark_error(account["_id"])
                        await _pc(progress_callback, "⚠️ Prompt input not found")
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

                    await _pc(progress_callback, "⏳ Generating image...")

                    image_url = await wait_for_image(page)

                    if image_url:
                        mark_success(account["_id"])
                        print(f"[worker] IMAGE: {image_url[:80]}...")
                        try:
                            updated_cookies = await ctx.cookies()
                            if updated_cookies:
                                accounts_col.update_one({"_id": account["_id"]}, {"$set": {"cookies": updated_cookies}})
                                print(f"[worker] Updated cookies saved to DB for {name}")
                        except Exception as cookie_err:
                            print(f"[worker] Failed to save updated cookies: {cookie_err}")
                        await _pc(progress_callback, f"✅ Done on `{name}`")
                        return {"success": True, "image_url": image_url, "account": name}

                    body = await page.text_content("body") or ""
                    reset_at = parse_limit_reset_time(body)
                    if reset_at:
                        mark_limited(account["_id"], reset_at)
                        left = (reset_at - datetime.now(timezone.utc)).total_seconds()
                        h, m = int(left // 3600), int((left % 3600) // 60)
                        await _pc(progress_callback, f"⏳ `{name}` limit — resets in {h}h {m}m")
                        continue

                    await _pc(progress_callback, "❌ No image generated")
                    return {"success": False, "error": "No image generated"}

                except Exception as e:
                    print(f"[worker] Exception during prompt run on {name}: {e}")
                    import traceback
                    traceback.print_exc()
                    mark_error(account["_id"])
                    if progress_callback:
                        await progress_callback(f"⚠️ {str(e)[:60]}")
                    continue

            return {"success": False, "error": "All accounts exhausted"}
        finally:
            await close_browser()


# ── Submit bulk ──

async def submit_bulk(prompts, image_size="1:1", retry=5, progress_callback=None):
    async with worker_lock:
        print(f"[worker] submit_bulk: {len(prompts)} prompts, size={image_size}")
        try:
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

                try:
                    ctx = _master["ctx"]
                    page = _master["page"]

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
                                try:
                                    updated_cookies = await ctx.cookies()
                                    if updated_cookies:
                                        accounts_col.update_one({"_id": account["_id"]}, {"$set": {"cookies": updated_cookies}})
                                        print(f"[worker] Updated cookies saved to DB for {name}")
                                except Exception as cookie_err:
                                    print(f"[worker] Failed to save updated cookies: {cookie_err}")
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
                except Exception as e:
                    print(f"[worker] Exception during bulk run on {name}: {e}")
                    return [{"success": False, "error": f"Exception: {str(e)[:60]}"} for _ in prompts]

            return [{"success": False, "error": "All accounts exhausted"} for _ in prompts]
        finally:
            await close_browser()


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

        # Not current account — launch temp browser
        try:
            p, temp_browser = None, None
            try:
                p = await asyncio.wait_for(async_playwright().start(), timeout=10)
                temp_browser = await asyncio.wait_for(p.chromium.launch(
                    headless=True, args=["--no-sandbox"]
                ), timeout=30)
                ctx = await temp_browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=USER_AGENT,
                )
                page = await ctx.new_page()
                await stealth_async(page)
                # Navigate first, then add cookies (fixes __Secure- cookie issues)
                try:
                    await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=20000)
                except Exception as e:
                    print(f"[worker] check_session: {label} nav error: {e}")
                    await ctx.close()
                    continue
                await asyncio.sleep(3)
                cookies = _sanitize_cookies(d.get("cookies", []))
                injected = 0
                for c in cookies:
                    try:
                        await ctx.add_cookies([c])
                        injected += 1
                    except:
                        pass
                if injected == 0:
                    print(f"[worker] check_session: {label} all cookies rejected")
                    await ctx.close()
                    continue
                await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(5)
                if LOGIN_URL in page.url:
                    name = d.get("profile_name") or label
                    expired.append({"label": label, "profile_name": name, "deleted": True})
                    accounts_col.delete_one({"_id": d["_id"]})
            finally:
                if temp_browser:
                    try:
                        await temp_browser.close()
                    except:
                        pass
                if p:
                    try:
                        await p.stop()
                    except:
                        pass
        except asyncio.TimeoutError:
            print(f"[worker] check_session: {label} timeout")
        except Exception as e:
            print(f"[worker] check_session: {label} error — {e}")

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


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    # Load env variables from root .env file
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(dotenv_path)
    
    from db import init_db
    
    async def run_manual_test():
        # Setup paths so we can import config correctly
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Connect to MongoDB
        await init_db()
        
        # Parse command line argument for prompt
        prompt = "a cute red panda eating bamboo, high resolution"
        if len(sys.argv) > 1:
            prompt = " ".join(sys.argv[1:])
            
        print(f"🚀 Running manual worker test for prompt: '{prompt}'")
        # Run headfully for local visibility
        os.environ["DEBUG"] = "true"
        
        # Trigger the generation
        result = await submit_prompt(prompt, image_size="1:1")
        print("\n✨ Test Result:")
        print(result)
        
    asyncio.run(run_manual_test())
