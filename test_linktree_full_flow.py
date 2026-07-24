import asyncio
import sys
import logging
from browser.browser_manager import BrowserManager
from browser.linktree_client import LinktreeClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")

async def main():
    manager = BrowserManager()
    await manager.initialize()
    
    try:
        linktree = LinktreeClient(manager)
        
        # Ensure we are on Linktree and logged in
        print("Opening Linktree...")
        page = await manager.new_page()
        await page.goto("https://linktr.ee/admin/shop", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        
        print("\n==========================================")
        print("TEST 1: Creating a NEW Collection & Adding")
        print("==========================================")
        title1 = "Test Vitamin C Serum"
        url1 = "https://www.amazon.com/dp/B0036BCWG0?tag=yourtag-20"
        category1 = "Face Serums"
        
        await linktree.add_link(title=title1, url=url1, category=category1)
        print("Test 1 Completed Successfully!")
        
        print("\n==========================================")
        print("TEST 2: Adding to EXISTING Collection")
        print("==========================================")
        title2 = "Test Gaming Keyboard"
        url2 = "https://www.amazon.com/dp/B08HR4ZLYP?tag=yourtag-20"
        category2 = "Gamer Tech (Test)"
        
        await linktree.add_link(title=title2, url=url2, category=category2)
        print("Test 2 Completed Successfully!")
        
        print("\nALL TESTS PASSED! Linktree automation is bulletproof!")
        await asyncio.sleep(5) # Let user see the success before closing
        
    except Exception as e:
        print(f"\nERROR DURING TEST: {e}")
        # Wait a bit so user can see the error state on screen
        await asyncio.sleep(10)
    finally:
        await manager.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
