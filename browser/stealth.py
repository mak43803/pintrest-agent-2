"""
Stealth — Anti-bot evasion techniques for Playwright.
======================================================

Pinterest uses advanced bot detection. This module provides techniques
to make the Playwright browser appear more human-like, such as:
    • Rotating realistic User-Agents
    • Modifying navigator properties (webdriver flag)
    • Randomizing viewport sizes slightly
    • Emulating human-like delays

Usage::

    from browser.stealth import apply_stealth, get_random_user_agent
    
    # ... during context creation
    context = await browser.new_context(user_agent=get_random_user_agent())
    await apply_stealth(context)
"""

from __future__ import annotations

import logging
import random
from typing import Any

from playwright.async_api import BrowserContext, Page

logger = logging.getLogger("pinterest_agent.browser.stealth")


# A list of modern, realistic user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
]


def get_random_user_agent() -> str:
    """Return a random, realistic User-Agent string."""
    ua = random.choice(USER_AGENTS)
    logger.debug("Selected User-Agent  │  ua=%s", ua[:50] + "...")
    return ua


async def apply_stealth(context_or_page: BrowserContext | Page) -> None:
    """
    Apply anti-bot evasion scripts to a context or page.

    This injects JavaScript that masks typical WebDriver signals:
    - Removes ``navigator.webdriver``
    - Mocks ``window.chrome``
    - Fixes ``navigator.plugins``

    Args:
        context_or_page: A Playwright BrowserContext or Page instance.
    """
    # JS script to mask webdriver presence
    stealth_script = """
        // 1. Remove webdriver flag
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // 2. Mock plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3]
        });

        // 3. Mock languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });

        // 4. Mock window.chrome (often checked by bot detectors)
        window.chrome = {
            runtime: {}
        };
    """
    
    await context_or_page.add_init_script(stealth_script)
    logger.info("Stealth evasion scripts applied.")


def get_randomized_viewport(base_width: int = 1280, base_height: int = 800) -> dict[str, int]:
    """
    Generate a slightly randomized viewport size.
    
    Bot detectors sometimes flag exact standard dimensions.
    This adds a small jitter to make it look like a manually resized window.

    Args:
        base_width:  Target width.
        base_height: Target height.

    Returns:
        Dict with 'width' and 'height'.
    """
    # Jitter between -20 and +20 pixels
    w_jitter = random.randint(-20, 20)
    h_jitter = random.randint(-20, 20)
    
    width = max(800, base_width + w_jitter)
    height = max(600, base_height + h_jitter)
    
    logger.debug("Randomized viewport  │  %dx%d", width, height)
    return {"width": width, "height": height}
