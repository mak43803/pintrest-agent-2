"""
Amazon Client — Playwright-based scraper and affiliate link generator.
========================================================================

Extracts product details (title, description, high-res images) from
Amazon URLs and generates Affiliate tags automatically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from browser.browser_manager import BrowserManager

logger = logging.getLogger("pinterest_agent.browser.amazon")


@dataclass
class AmazonProduct:
    """Extracted data from an Amazon product page."""
    title: str
    description: str
    image_url: str
    affiliate_url: str


class AmazonClient:
    """
    Automates interaction with Amazon to fetch product details
    and generate affiliate links.
    """

    def __init__(self, manager: BrowserManager, affiliate_tag: str = "yourtag-20"):
        self.manager = manager
        self.affiliate_tag = affiliate_tag
        logger.info("AmazonClient initialized  │  tag=%s", self.affiliate_tag)

    @staticmethod
    def add_affiliate_tag(url: str, tag: str) -> str:
        """
        Append or replace the affiliate tag in an Amazon URL.
        """
        parsed = urlparse(url)
        query_dict = parse_qs(parsed.query)
        
        # Replace or add the tag
        query_dict["tag"] = [tag]
        
        # Rebuild URL
        new_query = urlencode(query_dict, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        
        return urlunparse(new_parsed)

    async def search_products(self, keyword: str) -> str | None:
        """
        Search Amazon for a keyword and return the URL of the first organic product.
        
        Args:
            keyword: The search term (e.g. "aesthetic mushroom lamp").
            
        Returns:
            The raw Amazon product URL, or None if no products found.
        """
        logger.info("Searching Amazon for: %s", keyword)
        context = self.manager.context
        page = await context.new_page()
        
        try:
            # Navigate to Amazon search
            search_url = f"https://www.amazon.com/s?k={keyword.replace(' ', '+')}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            
            logger.info("Simulating proper human research on Amazon Search...")
            
            # Slowly scroll down to view products
            for _ in range(8):
                await page.mouse.wheel(0, 600)
                await page.wait_for_timeout(2500)
                
            # Slowly scroll back up
            for _ in range(3):
                await page.mouse.wheel(0, -1200)
                await page.wait_for_timeout(2000)
            
            # Find the first product link containing /dp/ (Product detail page)
            first_product = page.locator('a[href*="/dp/"]').first
            
            if await first_product.count() > 0:
                href = await first_product.get_attribute("href")
                if href:
                    if not href.startswith("http"):
                        href = "https://www.amazon.com" + href
                    logger.info("Found product  │  url=%s", href)
                    return href
                    
            logger.warning("No products found for keyword: %s", keyword)
            return None
            
        except Exception as exc:
            logger.error("Failed to search Amazon: %s", exc)
            return None
            
        finally:
            await page.close()

    async def fetch_product_details(self, url: str) -> AmazonProduct:
        """
        Navigate to the Amazon product page and extract its metadata.
        
        Args:
            url: The raw Amazon product URL.
            
        Returns:
            AmazonProduct dataclass containing title, desc, image, and tagged URL.
        """
        logger.info("Fetching product details from: %s", url)
        context = self.manager.context
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Wait for Amazon lazy-loaded gallery JavaScript to populate main image
            await page.wait_for_timeout(3500)
            
            # 1. Extract Title
            title_loc = page.locator("#productTitle").first
            title = await title_loc.inner_text() if await title_loc.count() > 0 else "Unknown Product"
            title = title.strip()
            
            # 2. Extract Description (Feature Bullets)
            desc_loc = page.locator("#feature-bullets li span.a-list-item")
            bullets = await desc_loc.all_inner_texts()
            description = "\n".join(b.strip() for b in bullets if b.strip())
            if not description:
                description = f"Check out this amazing {title} on Amazon!"
                
            # 3. Extract High-Res Image (Strictly filtering out Amazon logos/icons/UI elements)
            def is_valid_product_image(url_str: str) -> bool:
                if not url_str or not url_str.startswith("http"):
                    return False
                u_low = url_str.lower()
                invalid_terms = ["logo", "amazon", "icon", "banner", "sprite", "pixel", "x-locale", "common", "nav", "prime", "badge", "btn", "button", ".gif"]
                return not any(term in u_low for term in invalid_terms)

            image_url = ""
            try:
                # 1. Main landing image & gallery selectors
                main_locators = page.locator("#landingImage, #imgBlkFront, #main-image, #imgTagWrapperId img, #altImages img, li.imageThumbnail img, #imageBlock img")
                count = await main_locators.count()
                for idx in range(count):
                    loc = main_locators.nth(idx)
                    hires = await loc.get_attribute("data-old-hires", timeout=1000)
                    if hires and is_valid_product_image(hires):
                        image_url = hires
                        break
                    
                    dyn = await loc.get_attribute("data-a-dynamic-image", timeout=1000)
                    if dyn and "http" in dyn:
                        import json
                        try:
                            dyn_dict = json.loads(dyn)
                            for k in reversed(list(dyn_dict.keys())):
                                if is_valid_product_image(k):
                                    image_url = k
                                    break
                            if image_url:
                                break
                        except Exception:
                            pass

                    src = await loc.get_attribute("src", timeout=1000) or ""
                    if is_valid_product_image(src):
                        image_url = src
                        break
            except Exception as e:
                logger.warning(f"Could not extract Amazon main image: {e}")

            # 2. Fallback scan across all media-amazon images on page
            if not is_valid_product_image(image_url):
                try:
                    all_imgs = page.locator("img[src*='media-amazon.com/images/I/']")
                    img_count = await all_imgs.count()
                    for idx in range(img_count):
                        s = await all_imgs.nth(idx).get_attribute("src") or ""
                        if is_valid_product_image(s):
                            image_url = s
                            logger.info("Extracted Amazon product image via media fallback: %s", image_url)
                            break
                except Exception as e:
                    logger.warning(f"Media fallback image check failed: {e}")

            if not is_valid_product_image(image_url):
                raise Exception(f"Failed to find valid Amazon product image URL (rejected logos/icons) on page: {url}")
            affiliate_url = self.add_affiliate_tag(page.url, self.affiliate_tag)
            
            logger.info("Successfully extracted Amazon product  │  title=%s", title[:30])
            
            return AmazonProduct(
                title=title,
                description=description,
                image_url=image_url,
                affiliate_url=affiliate_url
            )
            
        except Exception as exc:
            logger.error("Failed to fetch Amazon product: %s", exc)
            raise
            
        finally:
            await page.close()

    async def get_us_home_decor_best_sellers(self) -> str:
        """
        Scrape top products from Amazon US Home Decor Best Sellers.
        Returns a comma-separated string of product titles.
        """
        logger.info("Fetching Amazon US Home Decor Best Sellers...")
        context = self.manager.context
        page = await context.new_page()
        
        try:
            await page.goto("https://www.amazon.com/Best-Sellers/zgbs/home-garden-decor", wait_until="domcontentloaded", timeout=60000)
            logger.info("Simulating proper human research on Amazon Best Sellers...")
            
            # Wait for page to settle
            await page.wait_for_timeout(5000)
            
            # Slowly scroll down through the top products
            for _ in range(12):
                await page.mouse.wheel(0, 700)
                await page.wait_for_timeout(3000)
                
            # Scroll back up a bit
            for _ in range(3):
                await page.mouse.wheel(0, -1000)
                await page.wait_for_timeout(2000)
            
            texts = await page.locator('div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1, div.p13n-sc-truncate-desktop-type2, span._cDEzb_p13n-sc-css-line-clamp-2_EWgCb, div[class*="line-clamp"]').all_inner_texts()
            
            if not texts:
                texts = await page.locator('div#gridItemRoot a > span > div').all_inner_texts()
                
            valid_texts = set()
            for t in texts:
                t = t.strip()
                if t and len(t) > 5 and "Amazon" not in t:
                    valid_texts.add(t)
                    
            best_sellers = list(valid_texts)[:30]
            logger.info("Found %d products from Amazon Best Sellers.", len(best_sellers))
            return ", ".join(best_sellers)
            
        except Exception as exc:
            logger.error("Failed to fetch Amazon Best Sellers: %s", exc)
            return ""
            
        finally:
            await page.close()
