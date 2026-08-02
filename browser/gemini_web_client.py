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
You are the Chief SEO & Creative Director for "Baddies Home Aesthetics" — a luxury home decor publication targeting women in the USA 🇺🇸, UK 🇬🇧, and Canada 🇨🇦 (ages 24–55). Write in an elegant, high-converting Architectural Digest editorial tone.

STRICT GEOGRAPHIC ROUTING RULE (USA 🇺🇸, UK 🇬🇧, CANADA 🇨🇦 ONLY):
1. Target 100% of content strictly for female home decor shoppers in the United States 🇺🇸, United Kingdom 🇬🇧, and Canada 🇨🇦.
2. In Title, Description, Alt-Text, and Tags, explicitly embed Western geographic search terms (e.g., "Amazon US", "Sephora & Architectural Digest USA 2026", "UK Home Decor", "Shoppers CA Favorites", "Cozy Aesthetic Room USA").
3. STRICT EXCLUSION: Explicitly exclude India, South Korea, Asia, and non-Western regions. Route 100% of Pinterest impressions, indexing, and feed distributions exclusively to USA, UK, and Canada users!

Input variables:
Product Title: {product_title}
Product Description: {product_desc}
Allowed Boards: {", ".join(allowed_boards)}

Return ONLY a single valid JSON object with keys "title", "description", "alt_text", "tags", "board" and nothing else. Follow all hard constraints below exactly.

VIRAL PINTEREST 1M IMPRESSIONS SEO CONSTRAINTS:
1. HIGH-INTENT SEARCH TITLE (STRICTLY 60 TO 80 CHARACTERS MAXIMUM): Combine [Price/Dupe Hook (e.g. The $24 Amazon Wavy Mirror...)] + [Exact Product Keyword] + [Category Keyword] + [Style/Year 2026]. Must include high-volume search terms like "Aesthetic", "Cozy", "Viral", "Amazon Home Finds", "Room Inspo" so the Pin ranks #1 whenever users search on Pinterest. (Example: "The $24 Amazon Wavy Mirror For A Cozy Japandi Bedroom — Room Inspo 2026")
2. VIRAL PINTEREST LENS ALT TEXT (400–450 CHARACTERS - MAXIMUM VISUAL SEARCH SEO): Alt text MUST be a rich 400 to 450 character visual description. Detail exact product texture, materials, color palette, room setup, lighting style, aesthetic theme (Japandi, Hygge, Minimalist, Boho), and high-converting search keywords for Pinterest Visual Lens AI (e.g., "High quality editorial product photograph featuring {product_title} elegantly styled in a warm cozy room setting with natural ambient lighting, soft studio shadows, champagne travertine, and clean minimal Japandi aesthetic room decor details, optimized for Pinterest Visual Search indexing in USA UK Canada.").
3. 1M IMPRESSIONS VIRAL DESCRIPTION COPYWRITING (400–450 CHARACTERS MAX):
   - Sentence 1 (Emotional Curiosity Hook): Write a high-converting emotional hook highlighting the instant room transformation benefit.
   - Sentence 2 (Keyword Density & Search Intent): Blend high-volume search keywords (e.g. "Looking for the best aesthetic room decor, cozy bedroom lighting, and viral Amazon home finds for small apartment setup?").
   - Sentence 3 (High-CTR Outbound Call-To-Action): Clear instruction ("Shop on Amazon").
   - Sentence 4 (Hashtag Stack): 5 trending high-volume hashtags (e.g., "#AmazonHome #AestheticRoom #CozyLiving #JapandiDecor #HomeFinds2026"). End with "💾 Save this pin!" as the last line.
4. STRICT PRODUCT & BOARD MATCHING: Select the board from `Allowed Boards` that MOST DIRECTLY matches the product's exact category or room context.

Output JSON Format Example:
{{
  "title": "The $24 Amazon Wavy Mirror For A Cozy Japandi Bedroom — Room Inspo 2026",
  "description": "Transform your room into a warm cozy sanctuary with this viral aesthetic wavy wall mirror! Ideal for small apartment decor, reading nooks, aesthetic vanity setups, and luxury bedroom upgrades. Shop on Amazon. #AmazonHome #AestheticRoom #CozyLiving #JapandiDecor #HomeFinds2026 💾 Save this pin!",
  "alt_text": "High quality visual product shot of a minimal wavy wall mirror with a warm golden frame; styled on a clean Japandi wooden desk beside coffee table books and a ceramic vase; natural ambient sunlight mixing with soft shadows; editorial Architectural Digest aesthetic home decor styling targeting USA UK Canada.",
  "tags": "wavy mirror,aesthetic room decor,cozy bedroom lighting,japandi decor,room mirrors,tiktok room trends,amazon home finds,minimalist desk setup,wall decor,room inspo",
  "board": "Aesthetic Mirrors"
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

PRODUCT PRIORITIZATION RULES (100% STRICT HOME DECOR ONLY):
- 100% STRICT RULE: HOME DECOR, INTERIOR DESIGN, FURNITURE, LIGHTING & ORGANIZATION PRODUCTS ONLY.
- NEVER suggest beauty products, makeup, skincare, lip oils, perfumes, fashion, clothes, or books under any circumstances.

---------------------------------------------------------------
VIRAL AMAZON US, UK & CANADA HOME DECOR BESTSELLERS REFERENCE:
---------------------------------------------------------------
Choose dynamically from these #1 Amazon US Bestseller categories and items:
- 💡 High-Commission Lighting & Ambiance:
  * Dimmable Sunset Projection Lamp (Amber Glow)
  * Vintage Dimmable Candle Warmer Lamp
  * Mid-Century Mushroom Table Lamp
  * 3D Moon Desk Lamp & Star Projector Galaxy Light
  * Fairy String Curtain Lights with Remote
  * LED Under Cabinet Sensor Strip Lighting
- 🎓 US College Dorm & Apartment Essentials (HIGH IMPULSE US FEMALE BUYERS):
  * Aesthetic Photo Wall Collage Prints Kit
  * Checkered Y2K Throw Blanket & Area Rug
  * Arch Floor Standing Lamp with Pleated Shade
  * Clear Acrylic Floating Bookshelves Set
  * Full Length Standing LED Floor Mirror
  * Clear Acrylic Magnetic Fridge Dry Erase Calendar
- 🎀 Coquette & Clean Girl Room Aesthetic Trends:
  * Scalloped Frame Decorative Wall Mirror
  * Bow Ribbon Brass Wall Hooks
  * Fluted Glass Coffee Mugs Set with Glass Straws
  * Ribbed Pillar Scented Soy Candles Set
  * Cloud Shaped Tufted Pillow & Plush Accent Mat
- 🪞 Mirrors & Wall Aesthetics:
  * Wavy Irregular Wall Mirror (Frameless Aesthetic)
  * Full Length Arched Gold Metal Frame Mirror
  * Minimalist Line Art Canvas Prints Set (Gallery Wall)
  * Botanical Olive Branch Framed Canvas Prints
  * Boho Macrame Woven Wall Hanging Tapestry
- 🛋️ Furniture & Room Accents:
  * Walnut Wood Floating Entryway Console Table
  * Minimalist Floating Wall Shelves (Set of 3)
  * Bouclé Ergonomic Swivel Accent Chair
  * Velvet Round Storage Ottoman Pouf
  * Dark Espresso Wood Coffee Table Tray
- 🛌 Bedding & Cozy Textiles:
  * Chunky Cable Knit Throw Blanket (Neutral Ivory)
  * 100% Washed Linen Duvet Cover Set
  * Silk Satin Pillowcase Set for Hair & Skin
  * Boho Tufted Textured Throw Pillow Covers Set
  * Faux Sheepskin Fur Rug Runner
- ☕ Kitchen, Coffee Bar & Pantry Setup:
  * Bamboo Spice Jar Set with Minimalist Labels
  * Clear Glass Coffee Syrup Dispenser Set with Gold Pumps & Labels
  * Amber Glass Soap Dispenser Bottles Set with Pump
  * Ribbed Fluted Glass Drinking Cups Set with Straws
  * Nespresso Pod Acrylic Organizer Holder
- 🛁 Bathroom & Organization:
  * Bamboo Bathtub Tray Caddy
  * Real Marble Vanity Tray with Gold Handles
  * Clear Acrylic Cosmetics & Skincare Organizer
  * Under Sink Sliding Organizer Drawers Set

{trends_str}
{past_str}

CRITICAL FORMAT REQUIREMENTS:
- Return ONLY a single concrete physical home decor product name on line 1 (3 to 6 words max, e.g. "Minimalist Walnut Wood Floating Shelves").
- NEVER output design aesthetics (e.g. "Design Aesthetic Mid Century Modern", "Soft Minimalist"), section headers ("Product Focus", "Trend Alert"), or meta text.
- STRICTLY FORBIDDEN: NO section headers, NO emojis, NO markdown, NO meta-text like "Product Specifications", "Trend Alert", "Strategy Blueprint", "Features", "Product Focus", "Design Aesthetic", or "Product Recommendation".
- DO NOT write any introduction or explanation. Output NOTHING except the raw physical product search query.

Example: Aesthetic Wavy Wall Mirror
"""
        response = await self._send_prompt(prompt)
        
        import random
        import re
        fallback_decor = [
            "Aesthetic Sunset Projection Lamp",
            "Aesthetic Wavy Wall Mirror",
            "Mushroom Table Lamp",
            "Candle Warmer Lamp Vintage",
            "Chunky Knit Blanket Throw",
            "Bamboo Spice Jar Organizer Set",
            "Clear Acrylic Makeup Vanity Organizer",
            "Amber Glass Soap Dispenser Bottle Set",
            "Donut Ceramic Vase for Pampas Grass",
            "Fairy String Curtain Lights",
            "Checkered Tufted Area Rug",
            "Flame Air Diffuser Essential Oil Humidifier",
            "Pure Washed Linen Duvet Cover Set",
            "Walnut Wood Floating Wall Shelves",
            "Clear Glass Coffee Syrup Dispenser Set",
            "Full Length Arched Gold Metal Frame Mirror",
            "Acacia Wood Cutting Board Cheese Board",
            "Wabi Sabi Ceramic Decorative Flower Vase",
            "Cordless Rechargeable Crystal Touch Table Lamp",
            "Acrylic Pantry Bins Storage Containers"
        ]

        if response:
            lines = [l.strip().replace('"', '').replace('*', '').replace('`', '') for l in response.strip().split('\n') if l.strip()]
            meta_words = {
                "specification", "specifications", "features", "blueprint", "strategy", 
                "alert", "trend", "trends", "overview", "curated", "breakdown", "analysis", 
                "recommendation", "guide", "details", "ambiance", "category", "focus", 
                "placement", "ideas", "design aesthetic", "product focus", "styling placement",
                "featured home decor product pick"
            }
            physical_nouns = {
                "lamp", "light", "lights", "mirror", "tray", "rug", "shelves", "shelf", "table", 
                "chair", "vase", "blanket", "curtain", "organizer", "caddy", "clock", "sculpture", 
                "art", "pillow", "frame", "lighter", "holder", "box", "basket", "diffuser", 
                "dispenser", "board", "mat", "hook", "creations", "trunk", "mugs", "mug", "cups", 
                "cup", "pots", "pot", "pan", "kitchenware", "organizers", "drawers", "drawer", 
                "planter", "bedding", "duvet", "sheets", "towel", "rack", "bench", "ottoman", 
                "pouf", "tapestry", "prints", "print", "candle", "candles", "warmer", "projector", 
                "stand", "cabinet", "benches", "desk", "sofa", "couch", "bookend", "bookends", "planters"
            }
            
            for l in lines:
                l_clean = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27ff\u2b00-\u2bff\u2300-\u23ff\u2000-\u206f\u2700-\u27bf]', '', l)
                l_clean = re.sub(r'^\s*[%#\-\*\•\d\.\)]+\s*', '', l_clean).strip()
                for prefix in [
                    "Design Aesthetic:", "Design:", "Category:", "Product Focus:", "Product:", 
                    "Keyword:", "Selected product keyword:", "Recommended:", "Selected:", 
                    "Option:", "Feature:", "Trend:", "Style:", "Pick:", "Featured Home Decor Product Pick:"
                ]:
                    if l_clean.lower().startswith(prefix.lower()):
                        l_clean = l_clean[len(prefix):].strip()
                
                # Fix unclosed parentheses
                if l_clean.count('(') > l_clean.count(')'):
                    l_clean = l_clean.replace('(', ' ')
                elif l_clean.count(')') > l_clean.count('('):
                    l_clean = l_clean.replace(')', ' ')
                
                l_clean = re.sub(r'[/\\:&%\(\)\[\]"\'`]+', ' ', l_clean)
                l_clean = re.sub(r'\s+', ' ', l_clean).strip()

                # Clean trailing noise words
                words = l_clean.split()
                while words and words[-1].lower() in {"with", "for", "and", "or", "in", "by", "of", "set", "design", "style", "ideas", "focus", "aesthetic"}:
                    words.pop()
                l_clean = " ".join(words).strip()
                l_lower = l_clean.lower()

                if not l_clean or l_clean.startswith("#") or "why this" in l_lower or "trending home decor" in l_lower or "recommended home decor" in l_lower or l_lower.startswith("category"):
                    continue
                if any(w in l_lower for w in meta_words) or "/" in l or "%" in l:
                    continue
                    
                # Ensure candidate contains a physical product noun
                has_noun = any(w.lower() in physical_nouns for w in l_clean.split())
                if not has_noun:
                    continue
                    
                if len(l_clean) >= 8 and len(l_clean) <= 65 and len(l_clean.split()) >= 2:
                    return l_clean

        past_set = set(p.lower().strip() for p in (past_products or []))
        valid_fallbacks = [f for f in fallback_decor if f.lower().strip() not in past_set]
        if valid_fallbacks:
            return random.choice(valid_fallbacks)
        return random.choice(fallback_decor)

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
