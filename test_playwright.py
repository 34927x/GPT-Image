"""
Manual Playwright test script -- step-by-step ChatGPT automation debugging.
Run: python3 test_playwright.py

Steps:
1. Load cookies from MongoDB (or use --cookies flag with a JSON file)
2. Open browser (headful -- you can see it)
3. Navigate to chatgpt.com with cookies
4. Check if login works or redirects to auth/login
5. Navigate to /images page
6. Try to find prompt input
7. Type a test prompt and submit
8. Wait for image generation
9. Screenshots at every step in /tmp/pw-test/
"""

import asyncio, json, sys, os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# Create output dir
os.makedirs("/tmp/pw-test", exist_ok=True)

# --- Step 0: Load cookies ---
COOKIES_FILE = None  # set via --cookies flag
MONGO_MODE = True    # try MongoDB by default

async def load_cookies_from_mongo():
    """Try to load cookies from the bot's MongoDB"""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from src.config import MONGO_URI, MONGO_DB
        client = AsyncIOMotorClient(MONGO_URI)
        db = client[MONGO_DB]
        accounts = await db.accounts.find({"expired": {"$ne": True}}).to_list(10)
        if not accounts:
            print("[!] No accounts found in MongoDB")
            return None
        print(f"[+] Found {len(accounts)} accounts in MongoDB:")
        for i, acc in enumerate(accounts):
            label = acc.get("label", "unknown")
            limited = acc.get("limited", False)
            print(f"    [{i}] {label} (limited={limited})")
        # Use first non-limited account
        for acc in accounts:
            if not acc.get("limited"):
                print(f"[+] Using account: {acc.get('label', 'unknown')}")
                return acc["cookies"]
        # All limited, use first one anyway
        print(f"[!] All accounts limited, using first one anyway")
        return accounts[0]["cookies"]
    except Exception as e:
        print(f"[!] MongoDB load failed: {e}")
        return None

async def load_cookies_from_file(path):
    """Load cookies from a JSON file"""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "cookies" in data:
        return data["cookies"]
    print("[!] Invalid cookie file format")
    return None

async def main():
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    # Load cookies
    cookies = None
    if COOKIES_FILE:
        cookies = await load_cookies_from_file(COOKIES_FILE)
    elif MONGO_MODE:
        cookies = await load_cookies_from_mongo()

    if not cookies:
        print("[!] No cookies available. Use --cookies <file.json> or add accounts to MongoDB")
        return

    print(f"\n{'='*60}")
    print(f"  PLAYWRIGHT MANUAL TEST -- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # --- Step 1: Launch browser + create context+page (NO cookies) ---
    print("[Step 1] Launching Chromium + creating page (no cookies yet)...")
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=False,  # HEADFUL -- you can watch!
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--start-maximized",
        ]
    )

    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        locale="en-US",
    )

    page = await ctx.new_page()  # Browser window shows up here
    await Stealth().apply_stealth_async(page)
    print("[Step 1] DONE - Browser window visible now!")

    # --- Step 2: Wait 5 seconds ---
    print("[Step 2] Waiting 5 seconds (no cookies, blank page)...")
    await asyncio.sleep(5)
    print("[Step 2] DONE - 5 seconds complete")

    # --- Step 3: Navigate to chatgpt.com (NO cookies) ---
    print("[Step 3] Navigating to https://chatgpt.com (WITHOUT cookies)...")
    try:
        await page.goto("https://chatgpt.com", wait_until="networkidle", timeout=45000)
    except Exception as e:
        print(f"[!] Navigation error: {e}")

    await asyncio.sleep(3)
    await page.screenshot(path="/tmp/pw-test/01-after-nav.png")
    print(f"    URL after nav: {page.url}")
    print(f"    Screenshot: /tmp/pw-test/01-after-nav.png")
    print("[Step 3] DONE - Page loaded without cookies")

    # --- Step 4: Reload page ---
    print("[Step 4] Reloading page...")
    try:
        await page.reload(wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"[!] Reload error: {e}")
    print("[Step 4] DONE - Page reloaded")

    # --- Step 5: Inject cookies NOW (after page load) ---
    print(f"[Step 5] NOW injecting {len(cookies)} cookies into browser context...")
    
    same_site_pw = {"strict": "Strict", "lax": "Lax", "no_restriction": "None", "unspecified": "None"}
    allowed = {"name", "value", "domain", "path", "httpOnly", "secure", "sameSite", "expires"}
    
    sanitized_cookies = []
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
        sanitized_cookies.append(cleaned)

    injected = 0
    failed = 0
    for i, c in enumerate(sanitized_cookies):
        try:
            await ctx.add_cookies([c])
            injected += 1
        except Exception as err:
            failed += 1
            print(f"    [!] Cookie #{i} ({c.get('name')}) failed: {err}")

    print(f"[Step 5] DONE - {injected} injected, {failed} failed")
    print("    → Open DevTools > Application > Cookies > chatgpt.com to see")
    await asyncio.sleep(3)

    # --- Step 6: Go to chatgpt.com again (WITH cookies) ---
    print("[Step 6] Navigating to https://chatgpt.com (WITH cookies now)...")
    try:
        await page.goto("https://chatgpt.com", wait_until="networkidle", timeout=45000)
    except Exception as e:
        print(f"[!] Navigation error: {e}")

    await asyncio.sleep(5)
    await page.screenshot(path="/tmp/pw-test/01-after-nav.png")
    print(f"    URL after nav: {page.url}")
    print(f"    Screenshot: /tmp/pw-test/01-after-nav.png")

    # --- Step 7: Check login status ---
    print("[Step 7] Checking login status...")
    if "auth/login" in page.url:
        print("    [FAIL] Redirected to LOGIN PAGE -- cookies are EXPIRED!")
        print("    You need fresh cookies from the Chrome extension")
        await page.screenshot(path="/tmp/pw-test/02-login-page.png")
        input("\nPress Enter to close browser...")
        await browser.close()
        return
    else:
        print("    [OK] Still on chatgpt.com -- login seems valid")

    # --- Step 8: Dismiss popups ---
    print("[Step 8] Dismissing popups...")
    popup_selectors = [
        'button:has-text("Okay, let\'s go")',
        'button:has-text("Got it")',
        'button:has-text("Stay logged out")',
        'button:has-text("Continue")',
        'button:has-text("Dismiss")',
        'button:has-text("Okay")',
        '[aria-label="Close"]',
        '.btn-close',
    ]
    for sel in popup_selectors:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                print(f"    Clicked popup: {sel}")
                await asyncio.sleep(1)
        except:
            pass
    await page.screenshot(path="/tmp/pw-test/03-after-popups.png")

    # --- Step 9: Navigate to /images ---
    print("[Step 9] Navigating to https://chatgpt.com/images ...")
    try:
        await page.goto("https://chatgpt.com/images", wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"    Navigation error (non-fatal): {e}")

    await asyncio.sleep(5)
    await page.screenshot(path="/tmp/pw-test/04-images-page.png")
    print(f"    URL: {page.url}")
    print(f"    Screenshot: /tmp/pw-test/04-images-page.png")

    # --- Step 10: Find prompt input ---
    print("[Step 10] Looking for prompt input...")
    prompt_selectors = [
        '#prompt-textarea',
        'textarea',
        '[contenteditable="true"]',
        'div[contenteditable="true"]',
        '[data-message-author-role]',
    ]
    found_input = None
    for sel in prompt_selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=5000)
            if el and await el.is_visible():
                found_input = el
                print(f"    [OK] Found input with selector: {sel}")
                break
        except:
            pass

    if not found_input:
        print("    [FAIL] No prompt input found!")
        await page.screenshot(path="/tmp/pw-test/05-no-input.png")

        # Try Create buttons
        print("    Trying Create buttons...")
        create_selectors = [
            'button:has-text("Create")',
            'button:has-text("New image")',
            'button:has-text("New")',
            'a:has-text("Create")',
            '[data-testid="create-button"]',
            'button[aria-label*="Create"]',
        ]
        for sel in create_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    print(f"    Clicking: {sel}")
                    await btn.click()
                    await asyncio.sleep(3)
                    await page.screenshot(path="/tmp/pw-test/05-after-create.png")
                    break
            except:
                pass

        # Try again
        for sel in prompt_selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=5000)
                if el and await el.is_visible():
                    found_input = el
                    print(f"    [OK] Found input after Create click: {sel}")
                    break
            except:
                pass

    if not found_input:
        print("    [FAIL] Still no prompt input found. Check screenshots.")
        await page.screenshot(path="/tmp/pw-test/05-final-no-input.png")

        # Debug: dump page HTML
        html = await page.content()
        with open("/tmp/pw-test/page-dump.html", "w") as f:
            f.write(html)
        print("    Page HTML dumped to /tmp/pw-test/page-dump.html")

        input("\nPress Enter to close browser...")
        await browser.close()
        return

    # --- Step 11: Type test prompt ---
    test_prompt = "a cute cat wearing a top hat"
    print(f"[Step 11] Typing test prompt: '{test_prompt}'")
    await found_input.click(click_count=3)
    await asyncio.sleep(0.3)
    await page.keyboard.type(test_prompt, delay=10)
    await asyncio.sleep(1)
    await page.screenshot(path="/tmp/pw-test/06-prompt-typed.png")

    # --- Step 12: Find and click send button ---
    print("[Step 12] Looking for send button...")
    send_selectors = [
        '[data-testid="send-button"]',
        'button[type="submit"]',
        'button:has(svg.lucide-arrow-up)',
        'button[aria-label*="Send"]',
        'button:has-text("Generate")',
        'button:has-text("Send")',
    ]
    send_btn = None
    for sel in send_selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                send_btn = el
                print(f"    [OK] Found send button: {sel}")
                break
        except:
            pass

    if send_btn:
        await send_btn.click()
        print("    Clicked send button")
    else:
        print("    [WARN] No send button found, pressing Enter...")
        await page.keyboard.press("Enter")

    await asyncio.sleep(3)
    await page.screenshot(path="/tmp/pw-test/07-after-send.png")

    # --- Step 13: Wait for image ---
    print("[Step 13] Waiting for image generation (max 120s)...")
    image_selectors = [
        'img[src*="dalle"]',
        'img[src*="oaidalle"]',
        'img[src*="gpt-image"]',
        'img[alt*="DALL"]',
        'img[alt*="Generated"]',
    ]

    found_image = False
    page_closed = False
    for i in range(24):  # 24 * 5 = 120 seconds
        await asyncio.sleep(5)
        try:
            # Check if page is still alive
            current_url = page.url
        except Exception as e:
            print(f"    [ERROR] Page/browser closed unexpectedly: {e}")
            page_closed = True
            break

        for sel in image_selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    src = await el.get_attribute("src")
                    print(f"    [SUCCESS] Image found! src={src[:80]}...")
                    found_image = True
                    break
            except:
                pass
        if found_image:
            break

        # Check for rate limit text
        try:
            body = await page.text_content("body") or ""
            if "resets in" in body.lower():
                print("    [RATE LIMITED] Rate limit detected!")
                break
        except:
            print("    [WARN] Could not read page body (page may be loading)")
            pass

        print(f"    Waiting... ({(i+1)*5}s)")

    if not page_closed:
        try:
            await page.screenshot(path="/tmp/pw-test/08-final.png")
        except:
            pass

    # --- Summary ---
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    try:
        login_ok = 'auth/login' not in page.url
    except:
        login_ok = not page_closed
    print(f"  Login:       {'OK' if login_ok else 'FAILED'}")
    print(f"  Prompt input: {'Found' if found_input else 'NOT FOUND'}")
    print(f"  Image:       {'Generated' if found_image else 'NOT GENERATED'}")
    if page_closed:
        print(f"  Page status:  CLOSED (ChatGPT may have detected automation)")
    print(f"  Screenshots: /tmp/pw-test/")
    print(f"{'='*60}")

    input("\nPress Enter to close browser...")
    await browser.close()

if __name__ == "__main__":
    # Parse args
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--cookies" and i < len(sys.argv) - 1:
            COOKIES_FILE = sys.argv[i + 1]
            MONGO_MODE = False

    asyncio.run(main())
