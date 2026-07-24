import asyncio
from browser.browser_manager import BrowserManager

async def main():
    manager = BrowserManager()
    await manager.initialize()
    page = await manager.new_page()
    await page.goto("https://linktr.ee/admin/shop")
    await asyncio.sleep(8)
    await page.screenshot(path="shop_debug_list.png")
    
    # Check if Test Collection text exists
    print(f"Current URL: {page.url}")
    print(f"Page Title: {await page.title()}")
    html = await page.content()
    with open("shop_collections.html", "w", encoding="utf-8") as f:
        f.write(html)
    if "Test Collection" in html:
        print("Test Collection found in HTML.")
    else:
        print("Test Collection NOT found in HTML.")
        
    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
