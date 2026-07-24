"""
Test: Add an affiliate product to Linktree via the correct flow.
"""
import asyncio
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")

from browser.browser_manager import BrowserManager
from browser.linktree_client import LinktreeClient

async def main():
    print("🧪 Testing Linktree Affiliate Product Flow...")
    
    manager = BrowserManager()
    await manager.initialize()
    
    client = LinktreeClient(manager)
    
    # Check login
    logged_in = await client.check_login()
    print(f"📌 Logged in: {logged_in}")
    
    if not logged_in:
        print("❌ Not logged in! Run login_linktree.py first.")
        await manager.close()
        return
    
    # Test adding an affiliate product link
    test_url = "https://www.amazon.com/dp/B0G29ZZQWG?tag=savvyshop0965-20"
    test_title = "💖 medicube PDRN Pink Peptide Serum"
    
    print(f"\n📌 Adding affiliate product...")
    print(f"   Title: {test_title}")
    print(f"   URL: {test_url}")
    
    success = await client.add_link(title=test_title, url=test_url)
    
    if success:
        print("\n✅ Affiliate product added successfully!")
    else:
        print("\n❌ Failed to add affiliate product!")
    
    await manager.close()
    print("🛑 Done.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
