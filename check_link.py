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
        
    elements = page.locator('input[placeholder*="link"], textarea[placeholder*="link"]')
    count = await elements.count()
    print(f'Total elements with placeholder link: {count}')
    for i in range(count):
        el = elements.nth(i)
        tag = await el.evaluate('el => el.tagName')
        placeholder = await el.get_attribute('placeholder')
        print(f'Element {i}: <{tag}> placeholder="{placeholder}"')

    # Find the link input by other attributes
    link_inputs = page.locator('input[type="url"], input[name="link"], textarea[name="link"]')
    count2 = await link_inputs.count()
    print(f'Total elements by type/name: {count2}')
    for i in range(count2):
        el = link_inputs.nth(i)
        tag = await el.evaluate('el => el.tagName')
        placeholder = await el.get_attribute('placeholder')
        print(f'Element {i}: <{tag}> placeholder="{placeholder}"')

    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
