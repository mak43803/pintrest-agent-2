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
        
    elements = page.get_by_placeholder('Add your title')
    count = await elements.count()
    print(f'Total elements with placeholder Add your title: {count}')
    for i in range(count):
        el = elements.nth(i)
        tag = await el.evaluate('el => el.tagName')
        print(f'Placeholder Element {i}: <{tag}>')

    elements2 = page.get_by_placeholder('Add a title')
    count2 = await elements2.count()
    print(f'Total elements with placeholder Add a title: {count2}')
    for i in range(count2):
        el = elements2.nth(i)
        tag = await el.evaluate('el => el.tagName')
        print(f'Placeholder 2 Element {i}: <{tag}>')

    elements3 = page.locator('[contenteditable="true"]')
    count3 = await elements3.count()
    print(f'Total elements with contenteditable: {count3}')
    for i in range(count3):
        el = elements3.nth(i)
        html = await el.inner_html()
        print(f'contenteditable Element {i} html: {html[:100]}')
        
    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
