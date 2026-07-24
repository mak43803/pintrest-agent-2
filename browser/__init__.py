"""
Browser Module — Playwright-based browser automation for Pinterest.
===================================================================

Provides the automation layer for interacting with the Pinterest web
interface. Handles stealth evasion, session persistence, and high-level
operations like login and pin creation.

Quick Start::

    from browser import BrowserManager, PinterestClient

    manager = BrowserManager()
    await manager.initialize()

    client = PinterestClient(manager)
    if not await client.is_logged_in():
        await client.login("user@example.com", "password")

    await client.create_pin(...)
    await manager.close()

Public API:
    - BrowserManager    — Playwright lifecycle & session manager
    - PinterestClient   — High-level Pinterest actions
    - stealth           — Anti-bot evasion techniques
"""

from browser.browser_manager import BrowserManager
from browser.pinterest_client import PinterestClient
from browser.amazon_client import AmazonClient, AmazonProduct
from browser.gemini_web_client import GeminiWebClient
from browser import stealth

__all__ = [
    "BrowserManager",
    "PinterestClient",
    "AmazonClient",
    "AmazonProduct",
    "GeminiWebClient",
    "stealth",
]
