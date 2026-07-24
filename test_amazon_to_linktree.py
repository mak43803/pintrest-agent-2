import asyncio
import sys
import logging
from browser.browser_manager import BrowserManager
from browser.amazon_client import AmazonClient
from browser.linktree_client import LinktreeClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")

async def main():
    manager = BrowserManager()
    await manager.initialize()
    
    try:
        amazon = AmazonClient(manager)
        linktree = LinktreeClient(manager)
        
        print("\n==========================================")
        # Get a Gaming Headset from Amazon and get the affiliate link
        url = "https://www.amazon.com/dp/B07R4T19S6" # Razer Kraken Headset
        print(f"Fetching Amazon product details for {url}...")
        
        try:
            product = await amazon.fetch_product_details(url)
        except Exception as e:
            print(f"Failed to fetch from Amazon. Taking screenshot...")
            await manager.context.pages[0].screenshot(path=r"C:\Users\mazzu\.gemini\antigravity-ide\brain\44c35f6a-34ae-492b-a2ea-0e6f40144efe\amazon_error.png", full_page=True)
            raise e
            
        print(f"\nSuccessfully fetched from Amazon:")
        print(f"Title: {product.title}")
        print(f"Affiliate URL: {product.affiliate_url}\n")
        
        print("==========================================")
        print("PHASE 2: Adding to Linktree 'Gamer Tech (Test)'")
        print("==========================================")
        
        # Add the affiliate link to the Gamer Tech (Test) collection
        await linktree.add_link(
            title=product.title,
            url=product.affiliate_url,
            category="Gamer Tech (Test)"
        )
        
        print("\n==========================================")
        print("FULL INTEGRATION TEST COMPLETED SUCCESSFULLY!")
        print("==========================================")
        
    except Exception as e:
        print(f"\nERROR DURING TEST: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
