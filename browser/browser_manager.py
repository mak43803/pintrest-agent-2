"""
Browser Manager — Core Playwright lifecycle and session management.
=====================================================================

Manages the Playwright instance, Browser, and Context. Handles the
saving and loading of session cookies to disk so that the agent stays
logged into Pinterest across restarts.

Features:
    • Asynchronous Playwright context management
    • JSON-based cookie persistence for session resumption
    • Applies stealth modules to all new contexts
    • Graceful shutdown and resource cleanup

Usage::

    from browser.browser_manager import BrowserManager

    manager = BrowserManager()
    await manager.initialize()
    page = await manager.new_page()
    ...
    await manager.close()
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from browser.stealth import apply_stealth, get_random_user_agent, get_randomized_viewport
from config.settings import get_settings
from utils.exceptions import BrowserLaunchError

logger = logging.getLogger("pinterest_agent.browser.manager")


class BrowserManager:
    """
    Lifecycle manager for the Playwright browser.

    Handles starting/stopping the browser, creating contexts with
    anti-bot stealth enabled, and persisting cookies to maintain sessions.
    """

    def __init__(self) -> None:
        self._settings = get_settings().browser
        
        # Paths for session persistence
        from config.settings import PROJECT_ROOT
        self._session_file = PROJECT_ROOT / "config" / "pinterest_session.json"
        
        # Playwright internal state
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        
        logger.info(
            "BrowserManager initialized  │  headless=%s  slow_mo=%dms",
            self._settings.headless,
            self._settings.slow_mo,
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """Return True if the browser context is active."""
        return self._context is not None

    @property
    def context(self) -> BrowserContext:
        """Return the active BrowserContext, raising an error if none."""
        if not self._context:
            raise BrowserLaunchError("Browser context is not initialized. Call initialize() first.")
        return self._context

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """
        Start Playwright, launch the browser, and set up the context.

        Also loads any saved cookies to resume previous sessions.
        """
        if self.is_running:
            logger.debug("Browser is already running.")
            return

        try:
            logger.info("Starting Playwright...")
            self._playwright = await async_playwright().start()
            
            logger.info("Launching Chromium (Isolated Persistent Context)...")
            from config.settings import PROJECT_ROOT
            user_data_dir = str(PROJECT_ROOT / "browser_session")
            
            # When running headlessly, launch Playwright's built-in Chromium to avoid single-instance redirection
            # that forces Chrome to open a visible window if Chrome is already running.
            # When running headfully, use system Chrome (channel="chrome") so the user can easily log in.
            channel = None if self._settings.headless else "chrome"
            
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel=channel,
                headless=self._settings.headless,
                slow_mo=self._settings.slow_mo,
                ignore_default_args=["--enable-automation"],
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--password-store=basic",
                ],
                no_viewport=False,
            )
            self._browser = None  # No separate browser object for persistent context

            # Apply JS stealth evasions
            await apply_stealth(self._context)
            
            # Set default timeout
            self._context.set_default_timeout(self._settings.timeout_seconds * 1000)

            logger.info("BrowserManager initialized successfully with Isolated Chrome.")

        except Exception as exc:
            logger.error("Failed to initialize browser  │  error=%s", exc)
            await self.close()
            raise BrowserLaunchError(f"Failed to launch browser: {exc}") from exc

    async def close(self) -> None:
        """
        Close all Playwright resources.
        """
        if self._context:
            try:
                await self._context.close()
                logger.debug("Context closed.")
            except Exception as e:
                logger.warning("Error closing context: %s", e)
            finally:
                self._context = None

        if self._browser:
            try:
                await self._browser.close()
                logger.debug("Browser closed.")
            except Exception as e:
                logger.warning("Error closing browser: %s", e)
            finally:
                self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
                logger.debug("Playwright stopped.")
            except Exception as e:
                logger.warning("Error stopping playwright: %s", e)
            finally:
                self._playwright = None

        logger.info("BrowserManager shutdown complete.")

    # ── Page Management ────────────────────────────────────────────────

    async def new_page(self) -> Page:
        """
        Create and return a new Page in the current context.
        Self-heals and restarts the browser if the context has crashed or closed.
        """
        try:
            if not self._context:
                await self.initialize()
            page = await self._context.new_page()
            
            # Auto-dismiss/accept any dialogs (alerts, confirms, leave page warnings) globally
            import asyncio
            page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
            
            logger.debug("New page created.")
            return page
        except Exception as e:
            if "closed" in str(e).lower() or "not initialized" in str(e).lower():
                logger.warning("Browser context appears to be closed/crashed. Attempting to restart...")
                await self.close()
                await self.initialize()
                page = await self._context.new_page()
                
                # Auto-dismiss dialogs on the recovered page as well
                import asyncio
                page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
                
                logger.info("Successfully recovered browser context and created new page.")
                return page
            raise

    # ── Session Management (Cookies) ───────────────────────────────────

    async def _save_session(self) -> None:
        """Extract cookies from the context and save to disk."""
        if not self._context:
            return

        try:
            cookies = await self._context.cookies()
            if not cookies:
                return

            self._session_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._session_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
                
            logger.info("Session saved  │  cookies=%d  path=%s", len(cookies), self._session_file.name)
        except Exception as exc:
            logger.error("Failed to save session cookies: %s", exc)

    async def _load_session(self) -> None:
        """Load cookies from disk and inject into the context."""
        if not self._context or not self._session_file.exists():
            return

        try:
            with open(self._session_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
                
            if cookies:
                await self._context.add_cookies(cookies)
                logger.info("Session loaded  │  cookies=%d", len(cookies))
        except Exception as exc:
            logger.error("Failed to load session cookies: %s", exc)
