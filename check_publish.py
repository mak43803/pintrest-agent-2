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
        
    elements = page.get_by_text('Publish')
    count = await elements.count()
    print(f'Total elements with text Publish: {count}')
    
    for i in range(count):
        el = elements.nth(i)
        tag = await el.evaluate('el => el.tagName')
        classes = await el.evaluate('el => el.className')
        print(f'Element {i}: <{tag} class="{classes}">')
            
    await manager.close()

if __name__ == '__main__':
    asyncio.run(main())
