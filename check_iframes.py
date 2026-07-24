import asyncio
from browser.browser_manager import BrowserManager
from browser.pinterest_client import PinterestClient

async def main():
    manager = BrowserManager()
    await manager.initialize()
    
    client = PinterestClient(manager)
    page = await client._get_page()
    
    await page.goto('https://www.pinterest.com/pin-builder/')
    await page.wait_for_timeout(5000)
    for _ in range(3):
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(500)
        
    print(f"Main page URL: {page.url}")
    
    # Check top level frames
    iframes = page.frames
    print(f'Total frames: {len(iframes)}')
    for f in iframes:
        print(f'Frame URL: {f.url}')
        try:
            publish_buttons = f.locator("button", has_text="Publish")
            count = await publish_buttons.count()
            print(f'Publish buttons in this frame: {count}')
            
            if count > 0:
                print("Found it!")
        except Exception as e:
            print(f'Error accessing frame: {e}')
            
    await manager.close()

if __name__ == '__main__':
    asyncio.run(main())
