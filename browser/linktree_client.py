"""
Linktree Client — High-level Linktree actions using Playwright.
===================================================================

Provides specific, high-level methods to interact with Linktree.
Encapsulates login via Google accounts and link adding automation.
"""

from __future__ import annotations

import logging
import os
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from browser.browser_manager import BrowserManager
from utils.exceptions import BrowserNavigationError, ElementNotFoundError

logger = logging.getLogger("pinterest_agent.browser.linktree")


class LinktreeClient:
    """
    High-level automation client for Linktree to add affiliate links.
    """

    BASE_URL = "https://linktr.ee"

    def __init__(self, manager: BrowserManager) -> None:
        self._manager = manager
        self._page: Page | None = None
        logger.info("LinktreeClient initialized.")

    async def _get_page(self) -> Page:
        """Return the active page, creating one if necessary."""
        if not self._page or self._page.is_closed():
            self._page = await self._manager.new_page()
        return self._page

    async def is_logged_in(self) -> bool:
        """
        Check if currently authenticated in Linktree.
        Navigates to the admin panel and checks for dashboard visibility.
        """
        page = await self._get_page()
        try:
            logger.info("Checking Linktree login status...")
            await page.goto(f"{self.BASE_URL}/admin", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            
            # If redirected to universal-login or login page, we are not logged in
            current_url = page.url
            if "login" in current_url.lower() or "universal-login" in current_url.lower():
                logger.info("Not logged in to Linktree (redirected to login).")
                return False
                
            # If the current URL contains admin, we are authenticated (since Linktree redirects unauthenticated users)
            if "admin" in current_url.lower():
                logger.info("Successfully authenticated to Linktree (URL contains 'admin').")
                return True
                
            # Look for Add link button or dashboard indicators
            add_btn_count = await page.locator('button:has-text("Add link"), button:has-text("Add"), [data-testid="admin-navigation-add-link"]').count()
            if add_btn_count > 0:
                logger.info("Successfully authenticated to Linktree (Found Add button).")
                return True
                
            logger.info("Dashboard elements not detected. Assuming not logged in.")
            return False
        except Exception as e:
            logger.debug(f"Error checking Linktree login: {e}")
            return False

    async def login(self) -> bool:
        """
        Perform login via Continue with Google.
        """
        page = await self._get_page()
        try:
            logger.info("Navigating to Linktree login page...")
            # Navigate to login page
            try:
                await page.goto(f"{self.BASE_URL}/login", wait_until="commit", timeout=30000)
            except Exception as e:
                logger.warning(f"Navigating to login page warning: {e}")
                
            # Check if we were already logged in and got auto-redirected to the admin page
            current_url = page.url
            if "admin" in current_url.lower() and "login" not in current_url.lower():
                logger.info("Redirected to Linktree admin page automatically. Already logged in!")
                return True
                
            logger.info("Waiting for Google login button to render...")
            
            # Formulate selectors that are commonly used for Google login
            google_selectors = [
                'descope-button:has-text("Continue with Google")',
                ':text("Continue with Google")',
                'button[id*="google" i]',
                'descope-button#google-login',
                'button[data-testid="google-login-button"]',
                '[id*="google" i]'
            ]
            
            # Wait for any of the selectors to become visible (with up to 15s timeout)
            google_btn = None
            for selector in google_selectors:
                try:
                    loc = page.locator(selector).first
                    await loc.wait_for(state="attached", timeout=3000)
                    if await loc.count() > 0:
                        google_btn = loc
                        break
                except Exception:
                    continue
                    
            if not google_btn:
                # One last try with a broad selector and wait
                try:
                    await page.wait_for_selector(':text("Continue with Google"), [id*="google" i]', timeout=10000)
                    google_btn = page.locator(':text("Continue with Google"), [id*="google" i]').first
                except Exception as wait_exc:
                    logger.error(f"Timeout waiting for Google login button elements: {wait_exc}")
                    
            if not google_btn:
                logger.error("Could not find 'Continue with Google' button on Linktree login page.")
                return False

            logger.info("Clicking 'Continue with Google' button...")
            await google_btn.click(force=True)
            await page.wait_for_timeout(5000)

            # Check if we are on accounts.google.com page
            if "accounts.google.com" in page.url:
                logger.info("On Google accounts page. Checking for account selectors...")
                # If there is a list of accounts, click the first one or the one matching "thehadit"
                for acc_selector in [
                    '[data-email*="thehadit" i]',
                    '[data-authuser="0"]',
                    'div[role="link"] div:has-text("thehadit")',
                    'div[role="link"]',
                    'li:has-text("thehadit")',
                    '[data-email]'
                ]:
                    acc_loc = page.locator(acc_selector).first
                    if await acc_loc.count() > 0:
                        logger.info(f"Clicking Google account: {acc_selector}")
                        await acc_loc.click(force=True)
                        await page.wait_for_timeout(5000)
                        break

            # Wait for admin redirect
            logger.info("Waiting for redirection to Linktree admin...")
            for _ in range(15):
                if "admin" in page.url.lower():
                    logger.info("Login successful! Navigated to Linktree admin.")
                    return True
                await page.wait_for_timeout(1000)

            # Final check
            if await self.is_logged_in():
                return True

            logger.error("Failed to redirect to admin page after login.")
            return False

        except Exception as e:
            logger.error(f"Failed to log in to Linktree: {e}")
            return False

    async def add_link(self, title: str, url: str, category: str = "") -> bool:
        """
        Add a product link to the Linktree Shop page under a collection.
        """
        return await self.add_link_to_collection(title, url, category)

    async def add_link_to_collection(self, title: str, url: str, collection_name: str) -> bool:
        """
        Add the product affiliate link to Linktree Shop under a specific collection.
        If the collection doesn't exist, it creates it.
        """
        import time
        page = await self._get_page()
        is_collection = False
        try:
            logger.info(f"Adding product to Linktree Shop  │  title='{title}'  url='{url}'  collection='{collection_name}'")
            
            # Navigate to Shop
            logger.info("Navigating to Linktree Shop Admin page...")
            await page.goto(f"{self.BASE_URL}/admin/shop", wait_until="domcontentloaded", timeout=120000)
            
            # Wait for Shop to load
            logger.info("Waiting for Shop page to load...")
            shop_loaded = False
            for attempt in range(15):
                await page.wait_for_timeout(5000)
                try:
                    edit_btn = page.locator('button:has-text("Edit")').first
                    if await edit_btn.is_visible():
                        shop_loaded = True
                        logger.info("Shop page loaded successfully (found Edit button).")
                        break
                except:
                    pass
            
            if not shop_loaded:
                logger.warning("Shop page might not be fully loaded, continuing anyway...")

            # Dismiss dialogs/tips modals if any
            logger.info("Dismissing potential dialogs...")
            for _ in range(3):
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)
                
            for close_selector in [
                '[aria-label="Close"]',
                '[aria-label="Close dialog"]',
                'button:has-text("Close")',
                'button.close-button',
                '[data-testid="tips-dialog-done"]'
            ]:
                try:
                    close_btns = await page.locator(close_selector).all()
                    for btn in close_btns:
                        if await btn.is_visible():
                            logger.info(f"Clicking visible close button: {close_selector}")
                            await btn.click(force=True)
                            await page.wait_for_timeout(2000)
                except:
                    pass
                
            # Ensure we are on the Manage tab to see collections
            try:
                manage_tab = page.locator('button:has-text("Manage")').first
                if await manage_tab.is_visible():
                    logger.info("Switching to 'Manage' tab to access collections...")
                    await manage_tab.click(force=True)
                    await page.wait_for_timeout(5000)
            except:
                pass
                
            # Slowly scroll down to load any lazy-loaded collections on page
            try:
                logger.info("Scrolling all the way down to load all existing collections...")
                for _ in range(15):  # Increased to 15 scrolls to reach bottom of very long lists
                    await page.mouse.wheel(0, 2000)
                    await page.wait_for_timeout(1500)
                # Scroll back to top
                await page.mouse.wheel(0, -30000)  # Scroll all the way back up
                await page.wait_for_timeout(4000)
            except Exception as scroll_err:
                logger.debug(f"Scroll initialization skipped or failed: {scroll_err}")
                
            # Organize into specific collection
            if collection_name:
                import re
                # 1. Clean and strip trailing numerical suffixes (e.g. "Home Decor 2" -> "Home Decor")
                collection_name_clean = re.sub(r'\s+\d+$', '', collection_name.strip())
                logger.info(f"Targeting Linktree collection: '{collection_name_clean}' (original: '{collection_name}')")
                
                # Helper function to find fuzzy card match
                async def find_fuzzy_collection_card(target_name: str):
                    target_words = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', target_name) if w]
                    if not target_words:
                        return None
                    
                    logger.info(f"Searching for card containing 'Add products to' and words: {target_words}")
                    
                    # Safe Strategy: Inject JS to find the specific collection card containing the target name and the 'Add' button.
                    # This completely avoids Playwright's filter() false-positives where the root page container is matched.
                    try:
                        js_code = """(target_name) => {
                            // Clean up any previous targets
                            document.querySelectorAll('[data-bot-target]').forEach(el => el.removeAttribute('data-bot-target'));
                            
                            // Find elements like h3, p, span that contain the target name
                            const els = Array.from(document.querySelectorAll('h2, h3, p, span, div')).filter(e => 
                                e.innerText && e.innerText.toLowerCase().trim() === target_name.toLowerCase().trim()
                            );
                            if (els.length > 0) {
                                els[0].setAttribute('data-bot-target', 'true');
                                return true;
                            }
                            
                            // If exact match not found, try includes
                            const els2 = Array.from(document.querySelectorAll('h2, h3, p, span, div')).filter(e => 
                                e.innerText && e.innerText.toLowerCase().includes(target_name.toLowerCase().trim()) && e.innerText.length < 100
                            );
                            if (els2.length > 0) {
                                els2[0].setAttribute('data-bot-target', 'true');
                                return true;
                            }
                            return false;
                        }"""
                        
                        found = await page.evaluate(js_code, target_name)
                        if found:
                            card_locator = page.locator('[data-bot-target="true"]').first
                            logger.info(f"Match Found via JS for '{target_name}' card.")
                            return card_locator
                    except Exception as e:
                        logger.warning(f"JS Card lookup strategy failed: {e}")
                        
                    return None

                card = await find_fuzzy_collection_card(collection_name_clean)
                coll_exists = False
                
                if card:
                    try:
                        await card.scroll_into_view_if_needed()
                        await page.wait_for_timeout(6000)
                        coll_exists = True
                        logger.info(f"Collection card for '{collection_name_clean}' found via fuzzy matching.")
                    except Exception as scroll_err:
                        logger.debug(f"Scroll check error: {scroll_err}")
                
                if not coll_exists:
                    logger.info(f"Collection '{collection_name_clean}' not found in dashboard. Creating a new one using the new UI flow...")
                    
                    # Click main '+ Add' button
                    add_btn = page.get_by_role("button", name="Add", exact=True).first
                    await add_btn.wait_for(state="visible", timeout=120000)
                    await add_btn.click()
                    await page.wait_for_timeout(5000)
                    
                    # Wait for Add dialog/modal container to open
                    dialog = page.locator('dialog:visible, [role="dialog"]:visible').first
                    await dialog.wait_for(state="visible", timeout=60000)
                    
                    # Select "Collection" from menu options
                    coll_btn = dialog.get_by_text("Collection", exact=True).first
                    await coll_btn.click(force=True)
                    await page.wait_for_timeout(8000)
                else:
                    # Linktree UI update: Click the collection card itself to open it
                    logger.info(f"Clicking the collection card '{collection_name_clean}' to open it...")
                    await card.click(force=True)
                    await page.wait_for_timeout(8000)
                    
                    # Inside the opened collection modal, click the '+ Add' button
                    logger.info("Locating the '+ Add' button inside the collection modal...")
                    modal_add_btn = None
                    for selector in [
                        'dialog:visible button:has-text("+ Add")',
                        'dialog:visible button:has-text("Add products")',
                        'dialog:visible button:has-text("Add")',
                        'button:has-text("+ Add")',
                        'button:has-text("Add")'
                    ]:
                        loc = page.locator(selector).filter(visible=True).first
                        if await loc.count() > 0:
                            modal_add_btn = loc
                            break
                    
                    if modal_add_btn:
                        await modal_add_btn.click(force=True)
                        await page.wait_for_timeout(8000)
                    else:
                        raise Exception("Could not find '+ Add' button inside the opened collection modal!")

                title_already_filled = False
                if not coll_exists:
                    # Check for Linktree's 'Title First' UI variant (asks for title + Continue button before products)
                    await page.wait_for_timeout(4000)
                    try:
                        continue_btn = page.locator('dialog:visible button:has-text("Continue")').filter(visible=True).first
                        if await continue_btn.count() > 0:
                            logger.info("Detected 'Title First' UI variant! Filling collection title first...")
                            title_first_input = page.locator('dialog:visible input[type="text"]').filter(visible=True).first
                            if await title_first_input.count() > 0:
                                await title_first_input.fill(collection_name_clean)
                                await page.wait_for_timeout(2000)
                                await continue_btn.click(force=True)
                                await page.wait_for_timeout(8000)
                                title_already_filled = True
                    except Exception as e:
                        logger.debug(f"Title First check skipped: {e}")

                # COMMON STEP FOR BOTH (NEW UI FLOW):
                # Now we should be on the "Search products or paste a link" screen
                logger.info("Pasting product affiliate link in URL search input...")
                
                # First wait for the dialog/modal to fully render
                await page.wait_for_timeout(5000)
                
                # Use get_by_placeholder to find the visible search input safely
                search_input = None
                for _ in range(15):
                    loc = page.locator('input[placeholder*="Search products"], input[placeholder*="Paste URL"], input[type="url"]').filter(visible=True).first
                    if await loc.count() > 0:
                        search_input = loc
                        break
                    await page.wait_for_timeout(2000)
                
                if not search_input:
                    raise Exception("Timeout waiting for Search Input to become visible.")
                
                await search_input.focus()
                await page.wait_for_timeout(2000)
                await search_input.press_sequentially(url, delay=50)
                await page.wait_for_timeout(5000)
                
                logger.info("Waiting for product search result to load...")
                search_overlay = page.locator('[role="dialog"]:visible, dialog:visible').last
                
                # Target the circular purple '+' button or any 'Add' button on the product search result
                target = search_overlay.locator('button:has-text("+"), button[aria-label*="Add" i], button:has-text("Add")').first
                if await target.count() == 0:
                    target = search_overlay.locator('button').filter(has_text="Amazon").first
                if await target.count() == 0:
                    target = search_overlay.locator('button').first
                    
                await target.wait_for(state="visible", timeout=60000)
                logger.info("Clicking product card / add button...")
                
                # Try to get the actual '+' icon (purple background)
                plus_icon = target.locator('div.bg-brand-pansy, .rounded-full.bg-brand-pansy, svg').first
                if await plus_icon.count() > 0:
                    logger.info("Found '+' icon inside the card, clicking it...")
                    await plus_icon.click(force=True)
                else:
                    logger.info("Icon not found, clicking the card button itself...")
                    await target.click(force=True)
                    
                await page.wait_for_timeout(8000)
                
                # IF WE ARE CREATING A NEW COLLECTION, WE NEED TO SET THE TITLE NOW!
                if not coll_exists and not title_already_filled:
                    logger.info("Filling 'Collection title' in the new creation flow...")
                    title_input = None
                    for selector in [
                        'dialog:visible input[value=""]', # usually empty when new
                        'dialog:visible input[placeholder*="title" i]',
                        'dialog:visible input[type="text"]',
                        'input[placeholder*="title"]',
                        'input[type="text"]'
                    ]:
                        loc = page.locator(selector).first
                        if await loc.count() > 0 and await loc.is_visible():
                            title_input = loc
                            break
                    if title_input:
                        # Playwright fill might not clear effectively on some React inputs, so we double down
                        await title_input.click()
                        await title_input.fill(collection_name_clean)
                        await page.wait_for_timeout(3000)
                    else:
                        logger.warning("Could not find Collection title input after adding product!")
                
                # Click the final purple 'Save' / 'Add' / 'Done' button if visible
                try:
                    logger.info("Waiting for the final 'Save' or 'Done' button to appear...")
                    save_btn = None
                    for _ in range(10):  # Wait up to 20 seconds
                        for selector in ['button:has-text("Save")', 'button:has-text("Done")']:
                            loc = page.locator(selector).filter(visible=True).first
                            if await loc.count() > 0:
                                # Ensure it's not disabled by React state
                                is_disabled = await loc.get_attribute("disabled")
                                if is_disabled is None:
                                    save_btn = loc
                                    break
                        if save_btn:
                            break
                        await page.wait_for_timeout(2000)
                                
                    if save_btn:
                        logger.info("Clicking the final purple 'Save' / 'Done' button...")
                        await save_btn.click(force=True)
                        await page.wait_for_timeout(15000)
                    else:
                        logger.warning("Save button did not become visible or enabled!")
                except Exception as e:
                    logger.debug(f"Save button check failed: {e}")
                
            logger.info("Waiting 50 seconds for product to save to Linktree...")
            await page.wait_for_timeout(50000)  # Increased to 50000ms for safety
            
            # Save screenshot for confirmation
            try:
                screenshot_path = r"c:\Users\mazzu\OneDrive\Desktop\pintrest ai agent\linktree_after_add.png"
                await page.screenshot(path=screenshot_path)
                logger.info(f"Linktree post-addition screenshot saved to: {screenshot_path}")
            except Exception as ss_exc:
                logger.warning(f"Failed to capture post-addition screenshot: {ss_exc}")
                
            logger.info("Product added successfully to Linktree Shop!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add product to Linktree Shop: {e}")
            try:
                err_ss = f"logs/memory_error_{int(time.time())}.png"
                await page.screenshot(path=err_ss)
                logger.info(f"Linktree error screenshot saved to: {err_ss}")
            except:
                pass
            return False
