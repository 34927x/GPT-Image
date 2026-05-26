import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

from config import Account, accounts_col
from worker import PROFILES_DIR

async def main():
    accounts = Account.get_all()
    
    if not accounts:
        print("No accounts in database!")
        return

    print(f"Found {len(accounts)} accounts. Select one to manually login:")
    for i, a in enumerate(accounts):
        label = a.get('label', 'Unknown')
        print(f"[{i}] {label} ({a['_id']})")
        
    choice = input("\nEnter account number to login: ")
    try:
        idx = int(choice)
        account = accounts[idx]
    except:
        print("Invalid choice")
        return

    account_id = str(account["_id"])
    profile_dir = PROFILES_DIR / account_id
    
    print(f"\nOpening Google Chrome with profile for {account.get('label')}...")
    print(f"Profile directory: {profile_dir}")
    print("\n👉 INSTRUCTIONS: ")
    print("1. Chrome will open. If you see Cloudflare, solve it.")
    print("2. Log into ChatGPT manually if you are not logged in.")
    print("3. Once you see the ChatGPT prompt, close the browser window.")
    
    async with async_playwright() as p:
        chrome_path = "/usr/bin/google-chrome-stable"
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            executable_path=chrome_path,
            headless=False,
            viewport={"width": 1280, "height": 800}
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://chatgpt.com")
        
        # Wait for user to close browser
        try:
            await page.wait_for_event("close", timeout=0) # wait forever until user closes
        except:
            pass
            
    print("\n✅ Profile saved successfully! The bot will now use this active session.")

if __name__ == "__main__":
    asyncio.run(main())
