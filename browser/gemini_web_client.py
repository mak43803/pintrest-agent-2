"""
Gemini Web Client — Playwright automation for gemini.google.com
================================================================

Automates the Gemini Web UI to avoid needing an API key.
Requires the user to log in to Google once manually in the browser.
The session is then saved and reused.
"""

from __future__ import annotations

import json
import logging
import asyncio
from typing import Any
from dataclasses import dataclass

from browser.browser_manager import BrowserManager

logger = logging.getLogger("pinterest_agent.browser.gemini")


@dataclass
class PinterestSEOData:
    """The generated SEO data for a Pinterest Pin."""
    title: str
    description: str
    alt_text: str
    tags: str
    board: str


class GeminiWebClient:
    """
    Automates the gemini.google.com web interface for free AI processing.
    """

    def __init__(self, manager: BrowserManager):
        self.manager = manager
        logger.info("GeminiWebClient initialized (No API required).")

    async def _send_prompt(self, prompt: str, image_path: str | None = None) -> str:
        """
        Navigate to Gemini, enter the prompt and optional image, and scrape the response.
        """
        logger.info("Opening Gemini Web UI...")
        context = self.manager.context
        page = await context.new_page()
        
        try:
            await page.goto("https://gemini.google.com/u/1/app", wait_until="domcontentloaded")
            
            try:
                await page.wait_for_selector('rich-textarea, div[contenteditable="true"], [aria-label*="prompt"]', timeout=15000)
            except Exception:
                logger.error("Could not find Gemini chat input. Please run login_gemini.py to log in to Google!")
                return ""

            if image_path:
                logger.debug("Uploading image to Gemini...")
                try:
                    # 1. Click upload/add button to reveal file input or menu
                    add_btn = page.locator(
                        'button[aria-label*="Upload" i], button[aria-label*="Add" i], button[aria-label*="Attach" i], '
                        'button[aria-label*="file" i], button[aria-label*="tool" i], button[aria-label*="picker" i], '
                        'button[aria-label*="plus" i], button[data-test-id*="upload" i], button.uploader-button'
                    ).first
                    
                    if await add_btn.count() > 0:
                        try:
                            await add_btn.click(force=True, timeout=2500)
                            await page.wait_for_timeout(500)
                        except Exception:
                            pass

                    # 2. Check if input[type="file"] is now in DOM
                    file_input = page.locator('input[type="file"]').first
                    if await file_input.count() > 0:
                        await file_input.set_input_files(image_path)
                        logger.info("Successfully uploaded image to Gemini via file input.")
                        await page.wait_for_timeout(2000)
                    else:
                        # 3. Try clicking menu item for upload
                        upload_menu = page.locator('[role="menuitem"]:has-text("Upload"), [role="menuitem"]:has-text("File"), [data-test-id*="uploader"]').first
                        if await upload_menu.count() > 0:
                            async with page.expect_file_chooser(timeout=3000) as fc_info:
                                await upload_menu.click(force=True, timeout=2000)
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(image_path)
                            logger.info("Successfully uploaded image to Gemini via file chooser.")
                            await page.wait_for_timeout(2000)
                        else:
                            logger.info("Skipped Gemini visual upload (SEO generating directly from product details).")
                except Exception as e:
                    logger.debug("Gemini image upload note: %s", e)

            logger.debug("Typing prompt...")
            chat_locator = page.locator('rich-textarea, div[contenteditable="true"], [aria-label*="prompt"]').first
            await chat_locator.click()
            await page.wait_for_timeout(500)
            await page.keyboard.insert_text(prompt)
            
            await page.wait_for_timeout(1000)
            send_button = page.locator('button[aria-label*="Send"], button[aria-label*="Submit"]')
            if await send_button.count() > 0:
                await send_button.first.click()
            else:
                await chat_locator.press("Enter")
                
            logger.info("Waiting for Gemini to write response...")
            try:
                await page.wait_for_selector('button[aria-label*="Stop generating"]', timeout=10000)
                await page.locator('button[aria-label*="Stop generating"]').wait_for(state="hidden", timeout=60000)
            except Exception:
                await page.wait_for_timeout(15000)
                
            response_blocks = page.locator('message-content')
            count = await response_blocks.count()
            
            if count > 0:
                latest_response = await response_blocks.nth(count - 1).inner_text()
                return latest_response.strip()
            else:
                logger.error("Could not find response block in Gemini UI.")
                return ""
                
        except Exception as exc:
            logger.error("Gemini Web Automation failed: %s", exc)
            return ""
            
        finally:
            await page.close()

    async def analyze_ui_for_selector(self, screenshot_path: str, failed_selector: str, context: str) -> str:
        """
        Vision-based self-healing core.
        Uploads a screenshot of a broken page to Gemini and asks for the correct CSS selector.
        """
        prompt = f"""
You are an expert Automation QA Engineer and Playwright/CSS expert.
The automated agent failed to find a UI element on the screen using the CSS selector '{failed_selector}'.
Context of what we were trying to do: {context}

Look at the attached screenshot of the current UI. Identify the correct element and provide a robust CSS selector to interact with it.
If it's an email field, password field, or login button, provide the most robust identifier (e.g., `#password`, `input[type="password"]`, `button[type="submit"]`).

CRITICAL RULES:
1. Return ONLY the CSS selector string. Do not include any markdown, explanation, or code blocks.
2. The response must be a valid Playwright CSS selector.
3. If you cannot identify the element, return exactly: "ERROR: Not found"
"""
        response_text = await self._send_prompt(prompt, image_path=screenshot_path)
        clean_selector = response_text.replace("```css", "").replace("```", "").strip()
        if len(clean_selector) > 100 or " " in clean_selector and not any(c in clean_selector for c in ['[', '>', '.', '#']):
            logger.error(f"Gemini returned invalid selector format: {clean_selector}")
            return "ERROR: Invalid response"
            
        logger.info(f"Vision Self-Healing returned new selector: {clean_selector}")
        return clean_selector

    async def generate_image_and_seo(self, product_title: str, product_desc: str, image_path: str | None = None) -> tuple[str | None, PinterestSEOData]:
        """
        Ask Gemini to generate an aesthetic Pinterest image of the product AND the SEO text in one prompt.
        """
        allowed_boards = [
            "Viral Home Decor 2026", "TikTok Made Me Buy It", "Amazon Must Haves 2026",
            "Aesthetic Room Inspo", "Cozy Aesthetic Living", "Dream Bedroom Aesthetics",
            "Budget Room Makeover Finds", "Aesthetic Amazon Gadgets",
            "Aesthetic Room Decor", "Japandi Bedroom", "Coquette Room Aesthetic", "Minimalist Home",
            "Cozy Gaming Setup", "Dark Academia Room", "Organic Modern Living", "Scandinavian Home Decor",
            "Danish Pastel Room", "Y2K Room Decor", "Aesthetic Apartment Setup",
            "Desk Setup Inspiration", "Acrylic Organizers", "Kitchen Organization Hacks", "Luxury Bathroom Storage",
            "Small Space Storage Ideas", "Pantry Organization Inspo",
            "Sunset Lamp Aesthetic", "LED Room Lights", "Aesthetic Wall Decor", "Cozy Night Lights",
            "Coffee Bar Setup", "Matcha Station Aesthetic", "Aesthetic Glassware & Mugs", "Luxury Dining Decor",
            "Amazon Home Finds", "Apartment Decor Ideas", "Home Decor Gift Ideas", "Cozy Home Essentials",
            "Weekend Charcuterie & Hosting", "College Dorm Room Inspo", "Botanicals & Faux Olive Trees",
            "Cozy Autumn & Fall Home Decor", "Aesthetic Checkered Rugs & Mats", "Cozy Flame Diffusers",
            "Aesthetic Candles & Holders", "Aesthetic Throw Pillows & Linens", "Aesthetic Mirrors",
            "Aesthetic Pet Home Decor", "Luxury Laundry Room Hacks", "WFH & Aesthetic Office Setup",
            "Holiday & Festive Seasonal Decor", "Black Friday & Cyber Deals 2026",
            "Quiet Luxury Home Decor", "Wabi-Sabi Organic Living", "Neutral Apartment Decor",
            "Minimalist Home Organization", "Cozy Night In Aesthetics", "Luxury Bedroom Inspo",
            "Modern Kitchen Styling", "Aesthetic Spa Bathroom", "Boho Living Room Inspo",
            "Aesthetic Home Bar Setup", "Fall Season Room Vibe", "Aesthetic Desk Decor"
        ]
        prompt = f"""
You are the Chief SEO & Creative Director for "Baddies Home Aesthetics" — a luxury home decor publication targeting women in the USA, UK, Canada, Australia (ages 24–55). Write in an elegant, high-converting editorial tone.

Input variables:
Product Title: {product_title}
Product Description: {product_desc}
Allowed Boards: {", ".join(allowed_boards)}

Return ONLY a single valid JSON object with keys "title", "description", "alt_text", "tags", "board" and nothing else. Follow all hard constraints below exactly; if any constraint cannot be met, return {{"error":"<concise failure reason>"}}.

VIRAL PINTEREST 1M IMPRESSIONS SEO CONSTRAINTS:
1. HIGH-INTENT SEARCH TITLE (70-80 CHARACTERS EXACTLY): Combine [Emotional Hook/Problem Solver] + [Exact Product Keyword] + [Category Keyword] + [Style/Year 2026]. Must include high-volume search terms like "Aesthetic", "Cozy", "Viral", "Finds", "Ideas" so the Pin ranks #1 whenever users search for this product on Pinterest.
2. VIRAL PINTEREST LENS ALT TEXT (350–400 CHARACTERS - MAXIMUM VISUAL SEARCH SEO): Alt text MUST be a rich 350 to 400 character visual description (under Pinterest's 500 character limit). Detail exact product texture, materials, color palette, room setup, lighting style, aesthetic theme (Japandi, Hygge, Minimalist, Boho), and high-converting search keywords for Pinterest Visual Lens AI (e.g., "High quality visual product shot of a minimal sunset projection lamp casting a warm amber glow against a warm white wall; styled on a clean oak wood desk beside coffee table books and a ceramic matcha cup; natural ambient sunlight mixing with soft lamp lighting; editorial Pinterest home decor aesthetics USA UK Canada.").
3. 1M IMPRESSIONS VIRAL DESCRIPTION COPYWRITING (350–400 CHARACTERS MAX):
   - Sentence 1 (Emotional Curiosity Hook): Write a high-converting emotional hook highlighting the instant room transformation benefit.
   - Sentence 2 (Keyword Density & Search Intent): Naturally blend 5 to 7 high-volume long-tail search keywords relevant to the product and category (e.g. "Perfect for small apartment decor, aesthetic room refresh, cozy bedroom lighting, and viral Amazon finds USA UK Canada.").
   - Sentence 3 (High-CTR Outbound Call-To-Action): Clear instruction to buy (*"Tap the image or click the link below to shop on Amazon today! 🛒 Save this pin! 💾"*).
   - Sentence 4 (Hashtag Stack): 6 to 8 trending high-volume hashtags (*#AmazonHome #AestheticRoom #CozyLiving #JapandiDecor #RoomInspo #TikTokRoom #HomeFinds*).
4. STRICT PRODUCT & BOARD MATCHING: Select the board from `Allowed Boards` that MOST DIRECTLY matches the product's exact category or room context.

Output JSON Format Example:
{{
  "title": "Aesthetic Sunset Lamp for Cozy Japandi Bedroom Ideas & Mood Decor 2026",
  "description": "Transform your room into a warm cozy sanctuary with this viral dimmable sunset lamp! Ideal for reading nooks, aesthetic desk setups, small bedroom decor, mood lighting, and luxury apartment upgrades. Tap the link below to shop this exact viral find on Amazon today! 🛒 Save this pin to your mood board! 💾 #SunsetLamp #AestheticRoom #CozyBedroom #JapandiDecor #RoomInspo #TikTokRoom #AmazonHomeFinds",
  "alt_text": "High quality visual product shot of a minimal sunset projection lamp casting a warm amber golden glow against a clean white wall; styled on a clean Japandi wooden desk beside coffee table books and a ceramic matcha cup; natural ambient sunlight mixing with warm lamp glow; editorial Pinterest aesthetic home decor styling targeting USA UK Canada.",
  "tags": "sunset lamp,aesthetic room decor,cozy bedroom lighting,japandi decor,led room lights,tiktok room trends,amazon home finds,minimalist desk setup,mood lighting,room inspo",
  "board": "Sunset Lamp Aesthetic"
}}
"""
        response_text = await self._send_prompt(prompt, image_path=image_path)
        
        try:
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                clean_json = response_text[start_idx:end_idx + 1].strip()
            else:
                clean_json = response_text.replace("```json", "").replace("```", "").strip()
                
            data = json.loads(clean_json)
            parsed_title = data.get("title", product_title[:80]).strip()
            if len(parsed_title) > 80:
                parsed_title = parsed_title[:80]

            parsed_alt = data.get("alt_text", "").strip()
            if len(parsed_alt) < 350:
                visual_padding = f" High quality editorial product photograph featuring {product_title} elegantly styled in a warm cozy Japandi home decor room setting with soft ambient lighting, clean minimal aesthetics, natural shadows, and organic textures, optimized for Pinterest Visual Search indexing in USA, UK, and Canada."
                parsed_alt = (parsed_alt + visual_padding) if parsed_alt else visual_padding.strip()
            if len(parsed_alt) > 400:
                parsed_alt = parsed_alt[:400]

            parsed_desc = data.get("description", "Check out this amazing home decor product on Amazon!").strip()
            if len(parsed_desc) > 420:
                parsed_desc = parsed_desc[:420]

            seo_data = PinterestSEOData(
                title=parsed_title,
                description=parsed_desc,
                alt_text=parsed_alt,
                tags=data.get("tags", "home decor, aesthetic, room decor, amazon finds").strip(),
                board=data.get("board", "Amazon Home Finds").strip()
            )
            return None, seo_data
        except Exception as e:
            logger.error(f"Failed to parse SEO JSON: {e}")
            words = [w.strip(" ,.-!&()|:") for w in product_title.split()]
            clean_words = [w for w in words if len(w) > 3 and w.lower() not in ["amazon", "must-have", "with", "for", "from", "under", "bestseller", "basics", "value"]]
            tags_list = ["#AmazonHome", "#TikTokRoom", "#HomeDecor"]
            for w in clean_words[:3]:
                tags_list.append(f"#{w.capitalize()}")
            fallback_hashtags = " ".join(tags_list)

            fallback_desc = f"Upgrade your room with this viral {product_title}! Perfect for small apartment decor, aesthetic room refresh, cozy bedroom styling, college dorm setup, and luxury home organization. Tap the link or click the image to shop this exact find on Amazon today! 🛒 Save this pin to your mood board! 💾 {fallback_hashtags} #AmazonHomeFinds #RoomInspo"
            fallback_alt = f"High quality editorial product photograph featuring {product_title} elegantly styled in a warm cozy room setting with natural ambient lighting, soft shadows, and clean minimal Japandi aesthetic room decor details, optimized for Pinterest Visual Search USA UK Canada."[:400]
            
            return None, PinterestSEOData(
                title=product_title[:70], 
                description=fallback_desc, 
                alt_text=fallback_alt, 
                tags="home decor, aesthetic room, interior design, shopping", 
                board="Home Decor Finds"
            )

    async def generate_product_idea(self, niche: str = "trending home decor", past_products: list[str] = None, live_trends: str = "", google_trends: str = "", amazon_best_sellers: str = "") -> str:
        """
        Ask Gemini for a highly specific, trending product keyword using live Pinterest trends.
        """
        past_str = ""
        if past_products:
            past_str = "\nDO NOT suggest any of these products, as I have already posted them:\n" + "\n".join(f"- {p}" for p in past_products)

        trends_str = ""
        if live_trends:
            trends_str = f"\nLIVE PINTEREST TRENDS TODAY:\n{live_trends}\n(Use these to inspire your home decor product choice if relevant!)\n"

        prompt = f"""
###############################################################
PINTEREST SHOPPING TRENDS NAVIGATION
###############################################################

PRODUCT PRIORITIZATION RULES (CRITICAL FOR FAST SALES IN US/UK/CANADA):
- 100% Priority: HIGH-CONVERSION, TRENDING IMPULSE BUYS FOR WOMEN. You must ONLY select products that are highly viral and likely to sell quickly.

{trends_str}
{past_str}

Return only ONE final product per research cycle. Give me EXACTLY ONE highly specific, trending product search term that I should type into Amazon.
Do not give me a list. Do not use quotes. Just the raw search term.
Example: Aesthetic Wavy Wall Mirror
"""
        response = await self._send_prompt(prompt)
        
        if response:
            return response.strip().replace('"', "")
        return niche

    async def detect_viral_trend_bypass(self, trends_list: str, allowed_categories: list[str]) -> dict[str, Any] | None:
        """
        Ask Gemini if there is a strong viral home decor product trending in the trends list.
        """
        prompt = f"""
Analyze these trending search terms from Google Trends and Pinterest Trends:
Trends List: {trends_list}

Allowed Categories: {", ".join(allowed_categories)}

Is there any specific, concrete home decor product, lighting fixture, aesthetic furniture, room accessory, or organization item that is currently trending and has high search volume?
The product keyword must be suitable for searching on Amazon (e.g. "Sunset Lamp", "Acrylic Organizer", "Checkered Rug", "Wavy Mirror", "Mushroom Lamp"). Avoid broad terms like "Home" or general news topics.

Return ONLY a single valid JSON object with the following keys and nothing else:
If a strong trend is found:
{{
  "trend_detected": true,
  "product_keyword": "<specific product keyword, max 4 words>",
  "category": "<one category selected from Allowed Categories>"
}}

If no specific home decor product is trending:
{{
  "trend_detected": false
}}
"""
        response_text = await self._send_prompt(prompt)
        try:
            import re
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                candidate = data.get("product_keyword", "")
                candidate_lower = candidate.lower()
                is_generic = candidate_lower in ["trending home decor", "home decor product", "aesthetic decor"] or len(candidate) < 4
                if data.get("trend_detected") and data.get("product_keyword") and data.get("category") and not is_generic:
                    if data["category"] in allowed_categories:
                        return data
            return {"trend_detected": False}
        except Exception as e:
            logger.error("Failed to parse viral trend response: %s", e)
            return {"trend_detected": False}
