"""
Verification test for AmazonClient.search_products with isolated session tests
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from browser.browser_manager import BrowserManager
from browser.amazon_client import AmazonClient


async def run_single_search(kw: str):
    manager = BrowserManager()
    await manager.initialize()
    amazon = AmazonClient(manager)

    print(f"Testing Amazon search for: '{kw}'...")
    url = await amazon.search_products(kw)
    print(f"Result for '{kw}': {url}")
    await manager.close()

    assert url is not None and "amazon.com" in url, f"Failed to find product for '{kw}'"


async def test_amazon():
    test_keywords = [
        "Wavy Wall Mirror",
        "Electric Candle Lighter Rechargeable",
        "Scalloped Edge Lacquer Tray"
    ]

    for kw in test_keywords:
        await run_single_search(kw)
        await asyncio.sleep(2)

    print("✅ All isolated Amazon search tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_amazon())
