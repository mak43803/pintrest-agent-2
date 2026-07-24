import asyncio
import logging
from playwright.async_api import async_playwright
from pathlib import Path
from config.settings import PROJECT_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")
logger = logging.getLogger("login_playwright")

async def main():
    user_data_dir = str(PROJECT_ROOT / "browser_session")
    logger.info("Starting Playwright (Chrome GUI mode) to log in to Linktree...")
    
    async with async_playwright() as p:
        # Launch persistent context in headful mode (headless=False)
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 800},
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = await context.new_page()
        
        logger.info("Opening Linktree Login...")
        await page.goto("https://linktr.ee/login", wait_until="domcontentloaded")
        
        logger.info("=========================================================")
        logger.info("BROWSER WINDOW IS OPEN!")
        logger.info("Please log in to your Linktree Account in the opened Chrome window.")
        logger.info("Once you are logged in successfully and see your Linktree Admin dashboard,")
        logger.info("just wait here. This browser will automatically close in 2 minutes.")
        logger.info("=========================================================")
        
        # Wait 120 seconds
        for i in range(120, 0, -1):
            if i % 10 == 0:
                logger.info(f"{i} seconds remaining...")
            await asyncio.sleep(1)
            
        logger.info("Closing browser...")
        await context.close()
        logger.info("Linktree Session successfully saved!")

if __name__ == "__main__":
    asyncio.run(main())
