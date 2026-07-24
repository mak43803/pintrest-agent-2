"""
Pinterest Agent Core — The central orchestrator.
==================================================

Wires together all modules (Database, LLM, Browser, Tools, Memory)
and executes the End-to-End Affiliate workflow.

Usage::
    from agent.pinterest_agent import PinterestAgent
    import asyncio
    
    agent = PinterestAgent()
    asyncio.run(agent.run_affiliate_pipeline(niche="latest home decor products"))
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path

def extract_asin(url: str) -> str | None:
    """Extract Amazon ASIN from product URL."""
    if not url:
        return None
    # Match 10-character alphanumeric ASIN after /dp/ or /gp/product/ or /gp/video/ or /d/
    match = re.search(r'/(?:dp|gp/product|gp/video|d)/([A-Z0-9]{10})', url, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    # Fallback if URL is just an Amazon domain and contains a 10-char alphanumeric string
    if "amazon." in url.lower():
        match = re.search(r'([A-Z0-9]{10})', url)
        if match:
            return match.group(1).upper()
    return None

from config.settings import get_settings
settings = get_settings()
from database.database import Database
from database.init_db import create_database
from browser.browser_manager import BrowserManager
from browser.pinterest_client import PinterestClient
from browser.amazon_client import AmazonClient
from browser.gemini_web_client import GeminiWebClient
from browser.linktree_client import LinktreeClient
from tools.image_tools import ImageTools
from utils.logger import setup_logging
from utils.log_manager import LogManager
from utils.error_handler import setup_global_exception_handler, log_execution
from memory.memory_manager import MemoryManager

# Setup root logger for the entire application
setup_logging()
logger = logging.getLogger("pinterest_agent.core")


class PinterestAgent:
    """The main autonomous AI Agent for Pinterest Affiliate Marketing."""

    def __init__(self) -> None:
        logger.info("Initializing PinterestAgent...")
        
        # 1. Database
        db_path = Path("database/pinterest_ai_agent.db")
        self.db = Database(str(db_path))
        create_database(self.db)
        
        # 2. Logging & Crash Recovery
        self.log_manager = LogManager(self.db)
        setup_global_exception_handler(self.log_manager)
        
        # 3. Browser Clients
        import os
        self.browser_manager = BrowserManager()
        self.amazon = AmazonClient(self.browser_manager, os.getenv("AMAZON_AFFILIATE_TAG", "yourtag-20"))
        
        self.gemini = GeminiWebClient(self.browser_manager)
        self.linktree = LinktreeClient(self.browser_manager)
        
        self.pinterest = PinterestClient(self.browser_manager)
        self.pinterest.enable_vision_healing(self.db, self.gemini.analyze_ui_for_selector)
        
        # 4. Tools
        self.image_tools = ImageTools()
        
        # 6. Memory System
        self.memory = MemoryManager(self.db)
        
        self._is_initialized = False

    async def initialize(self) -> None:
        """Start background services like the browser manager."""
        if self._is_initialized:
            return
            
        logger.info("Starting browser manager...")
        await self.browser_manager.initialize()
        self._is_initialized = True

    async def shutdown(self) -> None:
        """Gracefully close all connections."""
        logger.info("Shutting down Agent...")
        await self.browser_manager.close()
        self.db.close()

    def choose_board_by_product(self, title: str, suggested_board: str = None) -> str:
        if suggested_board and suggested_board.strip() and suggested_board.strip() not in ["Amazon Home Finds", "Home Decor Finds"]:
            return suggested_board.strip()
            
        title_lower = title.lower()
        if any(w in title_lower for w in ["quiet luxury", "espresso", "walnut", "boucle swivel", "chocolate brown"]):
            board = "Quiet Luxury Home Decor"
        elif any(w in title_lower for w in ["wabi sabi", "raffia", "strawberry vase", "sculptural"]):
            board = "Wabi-Sabi Organic Living"
        elif any(w in title_lower for w in ["black friday", "cyber", "deal", "robotic vacuum", "dyson", "kitchenaid"]):
            board = "Black Friday & Cyber Deals 2026"
        elif any(w in title_lower for w in ["pet", "cat", "dog", "litter box", "scratcher"]):
            board = "Aesthetic Pet Home Decor"
        elif any(w in title_lower for w in ["laundry", "detergent", "dryer", "hamper"]):
            board = "Luxury Laundry Room Hacks"
        elif any(w in title_lower for w in ["ghost", "halloween", "christmas", "festive", "garland"]):
            board = "Holiday & Festive Seasonal Decor"
        elif any(w in title_lower for w in ["walking pad", "treadmill", "lumbar", "laptop stand"]):
            board = "WFH & Aesthetic Office Setup"
        elif any(w in title_lower for w in ["charcuterie", "cocktail", "wine", "coupe", "ice bucket", "shaker", "hosting"]):
            board = "Aesthetic Home Bar Setup"
        elif any(w in title_lower for w in ["dorm", "fridge stand", "wallpaper", "shoe organizer"]):
            board = "College Dorm Room Inspo"
        elif any(w in title_lower for w in ["olive tree", "eucalyptus", "botanical", "garland", "plant"]):
            board = "Botanicals & Faux Olive Trees"
        elif any(w in title_lower for w in ["sunset", "moon", "crystal touch"]):
            board = "Sunset Lamp Aesthetic"
        elif any(w in title_lower for w in ["diffuser", "humidifier", "flame"]):
            board = "Cozy Flame Diffusers"
        elif any(w in title_lower for w in ["candle", "taper candle", "candle holder", "wax warmer"]):
            board = "Cozy Night In Aesthetics"
        elif any(w in title_lower for w in ["lamp", "light", "led", "neon", "bulb", "projector", "night light", "sconce", "puck light"]):
            board = "LED Room Lights"
        elif any(w in title_lower for w in ["desk", "keyboard", "mouse", "monitor", "pen holder", "blotter"]):
            board = "Aesthetic Desk Decor"
        elif any(w in title_lower for w in ["kitchen", "pantry", "spice", "counter", "drawer divider", "backsplash"]):
            board = "Modern Kitchen Styling"
        elif any(w in title_lower for w in ["bathroom", "shower", "soap dispenser", "towel", "bath caddy", "vanity"]):
            board = "Aesthetic Spa Bathroom"
        elif any(w in title_lower for w in ["organizer", "storage", "acrylic", "bin", "shelf", "shelves", "basket", "drawer", "vacuum storage"]):
            board = "Minimalist Home Organization"
        elif any(w in title_lower for w in ["rug", "carpet", "mat", "jute", "runner"]):
            board = "Aesthetic Checkered Rugs & Mats"
        elif any(w in title_lower for w in ["checkered", "pillow", "blanket", "throw", "cushion", "comforter", "duvet", "linen", "knit"]):
            board = "Luxury Bedroom Inspo"
        elif any(w in title_lower for w in ["mirror", "asymmetric", "gold mirror"]):
            board = "Aesthetic Mirrors"
        elif any(w in title_lower for w in ["coffee", "frother", "matcha", "brewer", "iced coffee", "espresso"]):
            board = "Coffee Bar Setup"
        elif any(w in title_lower for w in ["glassware", "goblet", "pitcher", "tumbler", "cup", "mug", "bamboo lid"]):
            board = "Aesthetic Glassware & Mugs"
        elif any(w in title_lower for w in ["poster", "art", "print", "wall decor", "canvas", "picture light"]):
            board = "Aesthetic Wall Decor"
        elif any(w in title_lower for w in ["pumpkin", "fall", "autumn", "wreath", "harvest"]):
            board = "Fall Season Room Vibe"
        elif any(w in title_lower for w in ["tiktok", "viral", "dupe"]):
            board = "TikTok Made Me Buy It"
        else:
            board = "Neutral Apartment Decor"
            
        return board

    def check_is_duplicate(
        self,
        candidate_keyword: str | None = None,
        product_details: Any | None = None,
        seo_data: Any | None = None
    ) -> tuple[bool, str]:
        """
        Check if a candidate product/keyword/ASIN/title/affiliate link is already in the database.
        Returns: (is_duplicate: bool, reason: str)
        """
        with self.db.connection() as conn:
            # 1. Check candidate product keyword against product_name & title in DB
            if candidate_keyword:
                kw_clean = candidate_keyword.strip().lower()
                chk = conn.execute(
                    "SELECT product_name FROM products WHERE LOWER(product_name) = ? OR LOWER(title) = ?",
                    (kw_clean, kw_clean)
                ).fetchone()
                if chk:
                    return True, f"Product keyword '{candidate_keyword}' already published in DB ({chk['product_name']})"

            # 2. Check product_details (ASIN, Title, Affiliate Link)
            if product_details:
                # 2a. Check Amazon ASIN match
                if hasattr(product_details, "affiliate_url") and product_details.affiliate_url:
                    new_asin = extract_asin(product_details.affiliate_url)
                    if new_asin:
                        cursor = conn.execute("SELECT affiliate_link FROM products WHERE affiliate_link IS NOT NULL AND affiliate_link != ''")
                        for row in cursor.fetchall():
                            existing_asin = extract_asin(row["affiliate_link"])
                            if existing_asin == new_asin:
                                return True, f"Amazon ASIN '{new_asin}' has already been published on Pinterest"

                    # 2b. Check Exact Affiliate Link
                    chk_link = conn.execute(
                        "SELECT 1 FROM products WHERE affiliate_link = ?",
                        (product_details.affiliate_url,)
                    ).fetchone()
                    if chk_link:
                        return True, f"Affiliate URL '{product_details.affiliate_url}' already exists in DB"

                # 2c. Check Product Title
                if hasattr(product_details, "title") and product_details.title:
                    title_clean = product_details.title.strip().lower()
                    chk_title = conn.execute(
                        "SELECT 1 FROM products WHERE LOWER(title) = ? OR LOWER(product_name) = ?",
                        (title_clean, title_clean)
                    ).fetchone()
                    if chk_title:
                        return True, f"Product title '{product_details.title}' already exists in DB"

            # 3. Check seo_data (SEO Title, Description)
            if seo_data:
                if hasattr(seo_data, "title") and seo_data.title:
                    seo_title_clean = seo_data.title.strip().lower()
                    chk_seo = conn.execute(
                        "SELECT 1 FROM products WHERE LOWER(title) = ? OR LOWER(description) = ?",
                        (seo_title_clean, seo_title_clean)
                    ).fetchone()
                    if chk_seo:
                        return True, f"SEO Title '{seo_data.title}' already exists in DB"

        return False, ""


    def verify_quality(self, product_details: Any, seo_data: Any, image_path: str, board_name: str) -> bool:
        """Verify quality standards before publishing (STEP 6 validation)."""
        logger.info("Running Pre-Publish Quality Check...")

        # 1. Correct affiliate URL
        if not product_details.affiliate_url or not product_details.affiliate_url.startswith("http"):
            logger.error("Quality Check Failed: Invalid/missing affiliate URL.")
            return False

        # 2. Correct product image
        if not image_path or not os.path.exists(image_path):
            logger.error("Quality Check Failed: Pin image file not found.")
            return False

        # 3. Pinterest SEO complete (Title, Description, Alt text)
        if not seo_data.title or not seo_data.description or not seo_data.alt_text:
            logger.error("Quality Check Failed: Title, Description, or Alt text is missing.")
            return False

        # 4. Alt text added & length
        if len(seo_data.alt_text) < 15:
            logger.error("Quality Check Failed: Alt text is too short.")
            return False

        # 5. Correct board selected
        if not board_name:
            logger.error("Quality Check Failed: Board name is not selected.")
            return False

        # 6. Content uniqueness & US English character checks
        with self.db.connection() as conn:
            # Check for duplicate affiliate link to prevent re-posting the same product
            if product_details.affiliate_url:
                cursor = conn.execute(
                    "SELECT 1 FROM products WHERE affiliate_link = ? OR LOWER(title) = LOWER(?) OR LOWER(description) = LOWER(?)",
                    (product_details.affiliate_url, seo_data.title, seo_data.description)
                )
            else:
                cursor = conn.execute(
                    "SELECT 1 FROM products WHERE LOWER(title) = LOWER(?) OR LOWER(description) = LOWER(?)",
                    (seo_data.title, seo_data.description)
                )
                
            if cursor.fetchone():
                logger.error("Quality Check Failed: Duplicate Affiliate Link or SEO Title/Description already exists in DB.")
                return False

        logger.info("✅ Quality Check Passed successfully!")
        return True

    def optimize_alt_text(self, alt_text: str, board_name: str, niche: str) -> str:
        """
        Optimize Alt-Text with high-volume search query tags naturally integrated.
        Ensures length is strictly under 490 characters to avoid Pinterest UI cutoffs.
        """
        board_lower = board_name.lower()
        niche_lower = niche.lower()
        
        seo_phrases = []
        if any(x in board_lower or x in niche_lower for x in ["room", "aesthetic", "minimalist", "japandi", "coquette"]):
            seo_phrases = ["aesthetic room decor ideas", "pinterest bedroom aesthetic", "cozy room makeover", "tiktok room trends"]
        elif any(x in board_lower or x in niche_lower for x in ["desk", "office", "setup", "gaming"]):
            seo_phrases = ["cozy desk setup", "aesthetic gaming room", "minimalist desk accessories", "work from home aesthetic"]
        elif any(x in board_lower or x in niche_lower for x in ["lamp", "light", "sunset", "neon"]):
            seo_phrases = ["aesthetic room lighting", "sunset lamp aesthetic", "cozy ambient lighting", "led room lights"]
        elif any(x in board_lower or x in niche_lower for x in ["organize", "storage", "acrylic"]):
            seo_phrases = ["aesthetic room organization", "home organization hacks", "acrylic makeup storage", "clean girl aesthetic room"]
        elif any(x in board_lower or x in niche_lower for x in ["kitchen", "coffee", "matcha", "glass"]):
            seo_phrases = ["aesthetic coffee bar", "matcha station ideas", "kitchen organization", "aesthetic glassware"]
        else:
            seo_phrases = ["viral home decor", "amazon home finds", "apartment decor ideas", "cozy home aesthetic"]
            
        # Add clean niche reference
        niche_clean = niche.strip().replace("-", " ").lower()
        if niche_clean not in board_lower:
            seo_phrases.insert(0, f"{niche_clean} finds")
            
        # Construct natural SEO sentence
        seo_sentence = " Ideal for search queries relating to: " + ", ".join(seo_phrases) + "."
        
        # Merge and limit to 490 chars (Pinterest max: 500)
        combined = alt_text.strip()
        if len(combined) + len(seo_sentence) <= 490:
            combined += seo_sentence
        else:
            # Trim alt_text to make space
            allowed_len = 490 - len(seo_sentence)
            combined = combined[:allowed_len].strip() + seo_sentence
            
        return combined

    async def execute_task_with_memory(self, task_name: str, task_fn, *args, **kwargs) -> Any:
        """
        Execute a task within a self-learning memory cycle.
        """
        import time
        import traceback
        from datetime import datetime, timezone
        
        # 1. SEARCH MEMORY BEFORE THE TASK
        logger.info(f"Memory Check: Searching past memories for task: '{task_name}'...")
        query = f"Failed while trying to '{task_name}'"
        
        # Get raw SearchResult list to read metadata
        query_vector = await self.memory.long_term._embeddings.get_embedding(query)
        results = self.memory.long_term._store.search(query_vector, limit=3)
        
        relevant_memories = [r for r in results if r.score >= 0.6 and r.metadata.get("type") == "failure"]
        
        if relevant_memories:
            logger.info("Memory Check: Auto-tuning execution for '%s' using %d past memory learnings.", task_name, len(relevant_memories))
        else:
            logger.info("Memory Check: No prior issues recorded for task '%s'.", task_name)

        # 2. EXECUTE THE TASK
        start_time = time.time()
        try:
            result = await task_fn(*args, **kwargs)
            
            # 3. TASK SUCCEEDED: IF THERE WAS A PREVIOUS FAILURE, UPDATE IT (LEARNING)
            if relevant_memories:
                # Update the most similar past failure to record success strategy
                best_match = relevant_memories[0]
                meta = best_match.metadata
                
                # Update counters
                meta["success_count"] = meta.get("success_count", 0) + 1
                meta["confidence"] = min(1.0, meta.get("confidence", 0.5) + 0.1)
                meta["last_used"] = datetime.now(timezone.utc).isoformat()
                meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                meta["working_solution"] = f"Resolved on next try. Task completed successfully in {time.time() - start_time:.2f}s."
                
                # Update vector store
                self.memory.long_term._store.update(best_match.id, metadata=meta)
                logger.info(
                    "Learning event: Memory confidence increased to %.2f for solved task '%s' (success_count: %d).",
                    meta["confidence"], task_name, meta["success_count"]
                )
                
            return result

        except Exception as exc:
            # 4. TASK FAILED: CAPTURE RUNTIME FAILURE AND STACK TRACE
            logger.error(f"Task '{task_name}' failed. Capturing details for LTM...")
            
            tb_str = traceback.format_exc()
            now_iso = datetime.now(timezone.utc).isoformat()
            
            # Dynamically fetch current browser URL and page title
            current_url = "Unknown"
            browser_state = "No active page"
            screenshot_path = None
            try:
                pages = self.browser_manager.context.pages
                if pages:
                    active_page = pages[-1]
                    current_url = active_page.url
                    browser_state = f"Active Page Title: {await active_page.title()}"
                    
                    # Capture screenshot
                    os.makedirs("logs", exist_ok=True)
                    screenshot_path = f"logs/memory_error_{int(time.time())}.png"
                    await active_page.screenshot(path=screenshot_path)
            except Exception as e:
                logger.debug(f"Failed to capture browser state/screenshot: {e}")

            error_msg = str(exc)
            exc_type = type(exc).__name__
            
            # Search if we already have this exact failure in memory
            # Query for exact message similarity
            failure_query = f"Failed while trying to '{task_name}'. Error: {error_msg}"
            failure_vector = await self.memory.long_term._embeddings.get_embedding(failure_query)
            existing_failures = self.memory.long_term._store.search(failure_vector, limit=3)
            
            matching_failures = [r for r in existing_failures if r.score >= 0.8 and r.metadata.get("type") == "failure"]
            
            if matching_failures:
                # Merge with existing failure
                best_match = matching_failures[0]
                meta = best_match.metadata
                meta["failure_count"] = meta.get("failure_count", 0) + 1
                meta["confidence"] = max(0.0, meta.get("confidence", 0.5) - 0.1)
                meta["last_used"] = now_iso
                meta["updated_at"] = now_iso
                meta["stack_trace"] = tb_str  # Update with latest stack trace
                meta["url"] = current_url
                meta["browser_state"] = browser_state
                if screenshot_path:
                    meta["screenshot_path"] = screenshot_path
                
                self.memory.long_term._store.update(best_match.id, metadata=meta)
                logger.info(
                    "Memory updated: Merged duplicate failure memory for task '%s'. Confidence decreased to %.2f (failure_count: %d).",
                    task_name, meta["confidence"], meta["failure_count"]
                )
            else:
                # Create new failure memory
                content = f"Failed while trying to '{task_name}'. Error: {error_msg}"
                meta = {
                    "type": "failure",
                    "task_name": task_name,
                    "exception_type": exc_type,
                    "exception_message": error_msg,
                    "stack_trace": tb_str,
                    "url": current_url,
                    "browser_state": browser_state,
                    "screenshot_path": screenshot_path,
                    "confidence": 0.5,
                    "success_count": 0,
                    "failure_count": 1,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "last_used": now_iso,
                    "working_solution": "None recorded yet"
                }
                
                await self.memory.long_term.remember_failure(
                    context=task_name,
                    error_msg=error_msg,
                    **meta
                )
                logger.info("Memory created: New failure recorded in Long-Term Memory for task '%s'.", task_name)

            # Re-raise the exception so it propagates normally to the pipeline/scheduler
            raise

    @log_execution(module="agent.core")
    async def run_affiliate_pipeline(
        self,
        niche: str = "trending home decor products for US women",
        board_name: str = "Home Decor Finds",
        product_keyword: str | None = None
    ) -> bool:
        """
        Executes the fully autonomous End-to-End workflow with quality checks and dynamic board selection.
        Detects duplicate pins/products prior to asset creation/publishing, rejects duplicates, and automatically re-researches a fresh product idea.
        """
        if not self._is_initialized:
            await self.initialize()
            
        logger.info("Starting E2E Affiliate Pipeline for niche: '%s'", niche)
        
        # Fetch ALL previously posted products/titles from DB to avoid duplicates completely
        past_products = []
        with self.db.connection() as conn:
            cursor = conn.execute("SELECT DISTINCT product_name FROM products WHERE product_name IS NOT NULL AND product_name != ''")
            past_products.extend([row["product_name"] for row in cursor.fetchall()])
            cursor_t = conn.execute("SELECT DISTINCT title FROM products WHERE title IS NOT NULL AND title != ''")
            past_products.extend([row["title"] for row in cursor_t.fetchall()])

        current_keyword = product_keyword
        max_duplicate_retries = 5

        for cycle_attempt in range(max_duplicate_retries):
            logger.info("--- Pipeline Cycle Attempt %d/%d for niche: '%s' ---", cycle_attempt + 1, max_duplicate_retries, niche)

            # STEP 1: Research/Idea Generation (Anti-Duplicate Loop)
            async def step_research():
                logger.info("STEP 1: Fetching live US trends & Generating product idea...")
                live_trends = await self.pinterest.get_us_home_decor_trends()
                
                max_retries = 5
                candidate_keyword = None
                for attempt in range(max_retries):
                    candidate = await self.gemini.generate_product_idea(niche, past_products, live_trends, "", "")
                    candidate = self.parse_product_keyword(candidate)
                    
                    # Validate keyword contains no blocked terms and is not generic
                    candidate_lower = candidate.lower()
                    blocked_terms = ["pinterest", "google", "analysis", "trends", "passive income", "profits"]
                    is_generic = candidate_lower in ["trending home decor", "home decor product", "aesthetic decor"] or len(candidate) < 4
                    has_blocked = any(w in candidate_lower for w in blocked_terms)
                    
                    if is_generic or has_blocked:
                        logger.warning("Parsed keyword is generic or contains blocked terms: '%s'. Retrying attempt %d...", candidate, attempt + 1)
                        continue
                        
                    # Check against full DB & past_products
                    is_dup, dup_reason = self.check_is_duplicate(candidate_keyword=candidate)
                    if not is_dup and candidate not in past_products:
                        candidate_keyword = candidate
                        break
                    else:
                        logger.warning("Gemini generated duplicate keyword: '%s' (%s). Retrying research...", candidate, dup_reason)
                        past_products.append(candidate)
                else:
                    raise Exception("Failed to generate a unique home decor product keyword after multiple attempts.")
                return candidate_keyword

            if current_keyword:
                selected_keyword = self.parse_product_keyword(current_keyword)
                logger.info("Bypass Mode: Using pre-selected trending product keyword: '%s'", selected_keyword)
            else:
                try:
                    selected_keyword = await self.execute_task_with_memory("Research and Idea Generation", step_research)
                except Exception as e:
                    logger.error(f"Research failed: {e}")
                    return False

            logger.info("Selected product keyword: %s", selected_keyword)
            
            # Step 2: Amazon Sourcing
            async def step_amazon_sourcing():
                logger.info("STEP 2: Sourcing from Amazon for keyword '%s'...", selected_keyword)
                amazon_url = await self.amazon.search_products(selected_keyword)
                if not amazon_url:
                    raise Exception(f"Failed to find product '{selected_keyword}' on Amazon.")
                    
                return await self.amazon.fetch_product_details(amazon_url)
                
            try:
                product_details = await self.execute_task_with_memory("Amazon Sourcing", step_amazon_sourcing)
            except Exception as e:
                logger.error(f"Amazon Sourcing failed for '%s': {e}", selected_keyword)
                past_products.append(selected_keyword)
                current_keyword = None
                continue  # Retry research
                
            # Strict Anti-Book & Off-Niche Home Decor Filter
            if hasattr(product_details, "title") and product_details.title:
                t_low = product_details.title.lower()
                book_terms = ["paperback", "hardcover", "mass market", "kindle edition", "novel", "pages", "author", "isbn", "publisher"]
                decor_exceptions = ["vase", "holder", "box", "nook", "fake", "decorative", "display", "stand", "tray"]
                is_real_book = any(b in t_low for b in book_terms) and not any(d in t_low for d in decor_exceptions)
                if is_real_book:
                    logger.warning("🚫 NON-DECOR REAL BOOK REJECTED: '%s'. Skipping to fresh home decor category...", product_details.title)
                    past_products.append(selected_keyword)
                    current_keyword = None
                    continue

            # Anti-Duplicate Check: Extract ASIN / Title / Link and check database
            is_dup, dup_reason = self.check_is_duplicate(candidate_keyword=selected_keyword, product_details=product_details)
            if is_dup:
                logger.warning(
                    "⚠️ DUPLICATE PIN DETECTED BEFORE CREATION! %s. Rejecting candidate product and restarting research phase for a fresh product idea (Attempt %d/%d)...",
                    dup_reason, cycle_attempt + 1, max_duplicate_retries
                )
                past_products.append(selected_keyword)
                if hasattr(product_details, "title") and product_details.title:
                    past_products.append(product_details.title)
                current_keyword = None
                continue  # RE-RESEARCH! Loop back to Step 1

            # Step 3: Downloading Amazon product image first
            async def step_image_download():
                logger.info("STEP 3: Downloading Amazon product image first...")
                img_path = self.image_tools.download_image(product_details.image_url)
                if not img_path:
                    raise Exception(f"Failed to download image from URL: {product_details.image_url}")
                return img_path
                
            try:
                amazon_img_path = await self.execute_task_with_memory("Image Download", step_image_download)
            except Exception as e:
                logger.error(f"Image download failed: {e}")
                past_products.append(selected_keyword)
                current_keyword = None
                continue
            
            # Step 4: Image & SEO Generation via Gemini
            async def step_gemini_seo():
                logger.info("STEP 4: Generating Aesthetic Image & SEO via Gemini Web (Uploading Amazon image)...")
                gemini_img_path, seo_data = await self.gemini.generate_image_and_seo(
                    product_title=product_details.title,
                    product_desc=product_details.description,
                    image_path=amazon_img_path
                )
                if not seo_data or not seo_data.title or not seo_data.description:
                    raise Exception("Gemini Web returned invalid or empty SEO/title details.")
                return gemini_img_path, seo_data
                
            try:
                gemini_img_path, seo_data = await self.execute_task_with_memory("Gemini SEO Generation", step_gemini_seo)
            except Exception as e:
                logger.error(f"Gemini SEO Generation failed: {e}")
                past_products.append(selected_keyword)
                current_keyword = None
                continue
            
            # Double check SEO title uniqueness
            is_seo_dup, seo_dup_reason = self.check_is_duplicate(seo_data=seo_data)
            if is_seo_dup:
                logger.warning(
                    "⚠️ DUPLICATE SEO TITLE DETECTED! %s. Rejecting candidate and restarting research phase...",
                    seo_dup_reason
                )
                past_products.append(selected_keyword)
                current_keyword = None
                continue

            if gemini_img_path:
                logger.info("Successfully generated AI Image from Gemini: %s", gemini_img_path)
                raw_image_path = gemini_img_path
            else:
                logger.warning("Falling back to Amazon product image.")
                raw_image_path = amazon_img_path
                
            logger.info("Formatting image for Baddies Home Aesthetics Pinterest Pin...")
            try:
                import random

                def get_product_matched_overlay(raw_title: str, niche_context: str = "") -> tuple[str, str, str]:
                    """
                    Generates product-matched Category Label, Headline, and CTA for maximum CTR.
                    Strictly matches product title first to ensure lamps get LIGHTING, beds get BEDROOM, etc.
                    """
                    t_lower = (raw_title or "").lower()
                    n_lower = (niche_context or "").lower()

                    # 1. LIGHTING & AMBIANCE (Check title first!)
                    if any(k in t_lower for k in ["lamp", "light", "led", "sunset", "neon", "bulb", "projector", "sconce", "puck light", "night light"]):
                        labels = [
                            "AMAZON LIGHTING FIND",
                            "AESTHETIC ROOM GLOW",
                            "COZY LIGHTING HACK",
                            "AMAZON AMBIENT LIGHT",
                            "SUNSET LAMP EDIT",
                            "ROOM VIBES ESSENTIAL",
                            "BEDSIDE GLOW FIND",
                            "VIRAL LIGHTING FIND",
                            "LUXURY MOOD LIGHT"
                        ]
                        headlines = [
                            "The Aesthetic Lighting Upgrade You Need",
                            "The Cozy Home Upgrade Everyone Wants",
                            "Small Room Upgrade Big Difference",
                            "Luxury Room Lighting Under Budget",
                            "Cozy Ambient Lighting Starts Here",
                            "This Lamp Changes The Whole Room Vibe",
                            "Viral Glow Lamp Everyone Is Obsessed With",
                            "Affordable Mood Lighting That Looks Premium"
                        ]
                        ctas = ["Shop this ambient find →", "Get the lighting look →", "Tap to check Amazon price →", "Shop the vibe →"]

                    # 2. BEDROOM & THROW PILLOWS / BLANKETS / BEDS
                    elif any(k in t_lower for k in ["bed", "headboard", "pillow", "blanket", "throw", "bedroom", "linen", "bedding", "cushion", "duvet", "comforter", "mattress", "nightstand"]):
                        labels = [
                            "AMAZON BEDROOM FIND",
                            "COZY BEDDING EDIT",
                            "AESTHETIC THROW PILLOW",
                            "BEDSIDE ESSENTIAL",
                            "LUXURY BEDROOM HACK",
                            "AMAZON LINEN FAV",
                            "COZY ROOM DECOR",
                            "BEDROOM UPGRADE FIND"
                        ]
                        headlines = [
                            "The Cozy Bedroom Upgrade Everyone Wants",
                            "Cozy Living Starts In The Bedroom",
                            "Aesthetic Bedding That Looks Expensive",
                            "Make Your Bedroom Look Like A Luxury Hotel",
                            "Small Bedroom Upgrade Big Difference",
                            "The Softest Aesthetic Throw Pillows",
                            "Transform Your Bed into A Cozy Haven"
                        ]
                        ctas = ["Shop bedroom finds →", "Get the cozy look →", "Tap to shop Amazon link →", "Shop the bedroom edit →"]

                    # 3. KITCHEN & COFFEE / DRINKWARE
                    elif any(k in t_lower for k in ["kitchen", "coffee", "mug", "matcha", "spice", "counter", "pantry", "frother", "goblet", "pitcher", "utensil", "cookware", "pan ", "pot ", "cereal dispenser", "bamboo lid"]):
                        labels = [
                            "AMAZON KITCHEN FIND",
                            "COFFEE BAR MUST-HAVE",
                            "COZY KITCHEN EDIT",
                            "AMAZON KITCHEN FAV",
                            "KITCHEN ORGANIZER",
                            "AESTHETIC GLASSWARE",
                            "COUNTERTOP FAVORITE",
                            "PANTRY ESSENTIAL",
                            "VIRAL KITCHEN HACK",
                            "AMAZON KITCHEN MUST-HAVE"
                        ]
                        headlines = [
                            "Amazon's Favorite Kitchen Find",
                            "Make Your Kitchen Look Expensive",
                            "The Cozy Kitchen Upgrade Everyone Wants",
                            "Small Kitchen Upgrade Big Difference",
                            "Luxury Kitchen Finds Under Budget",
                            "The Ultimate Coffee Bar Setup",
                            "Aesthetic Glassware You Need In Your Kitchen",
                            "Transform Your Kitchen On A Budget"
                        ]
                        ctas = ["Shop the kitchen look →", "Tap for Amazon link →", "Shop this kitchen find →", "Get the look →"]

                    # 4. BATHROOM & VANITY
                    elif any(k in t_lower for k in ["bathroom", "shower", "towel", "soap", "vanity", "bath caddy", "dispenser"]):
                        labels = [
                            "AMAZON BATHROOM FIND",
                            "LUXURY VANITY EDIT",
                            "SPA AT HOME HACK",
                            "AMAZON BATH FAV",
                            "VANITY ORGANIZER",
                            "CLEAN BATHROOM ESSENTIAL",
                            "AESTHETIC TOWEL SET"
                        ]
                        headlines = [
                            "Turn Your Bathroom Into A Spa",
                            "Aesthetic Bath Finds That Look Expensive",
                            "Luxury Bathroom Upgrade Under Budget",
                            "Small Bathroom Upgrade Big Difference",
                            "The Clean Vanity Hack Everyone Loves"
                        ]
                        ctas = ["Shop bath collection →", "Get the spa look →", "Tap for Amazon link →", "Shop this bathroom edit →"]

                    # 5. RUGS & FLOORING
                    elif any(k in t_lower for k in ["rug", "carpet", "mat", "doormat", "runner", "jute"]):
                        labels = [
                            "AMAZON RUG FIND",
                            "AESTHETIC RUG EDIT",
                            "COZY TEXTILE FAV",
                            "CHECKERED RUG FIND",
                            "LIVING ROOM RUG",
                            "HIGH-END RUG DUPE"
                        ]
                        headlines = [
                            "The Aesthetic Rug That Anchors Any Room",
                            "Luxury Texture Under Budget",
                            "Statement Rug Everyone Asks About",
                            "Make Your Living Room Feel Cozy",
                            "High-End Looking Rug Finds On Amazon"
                        ]
                        ctas = ["Shop rug on Amazon →", "Get the look →", "Tap to check price →", "Discover the collection →"]

                    # 6. MIRRORS & WALL ART / DECOR
                    elif any(k in t_lower for k in ["mirror", "art", "print", "poster", "wall decor", "frame", "canvas", "picture light", "wallpaper"]):
                        labels = [
                            "AMAZON WALL DECOR",
                            "AESTHETIC MIRROR FIND",
                            "GALLERY WALL EDIT",
                            "ROOM ART FAVORITE",
                            "STATEMENT WALL DECOR",
                            "AMAZON MIRROR DUPE"
                        ]
                        headlines = [
                            "The Aesthetic Mirror Everyone Wants",
                            "Make Empty Walls Look Like An Art Gallery",
                            "Statement Wall Decor Under Budget",
                            "Small Space Wall Upgrade Big Difference",
                            "Luxury Wall Decor Finds You Need"
                        ]
                        ctas = ["Shop wall decor →", "Get the look →", "Tap for product link →", "Shop the art edit →"]

                    # 7. STORAGE & ORGANIZATION
                    elif any(k in t_lower for k in ["desk", "organizer", "storage", "shelf", "shelves", "acrylic", "bin", "drawer", "closet", "hanger"]):
                        labels = [
                            "AMAZON STORAGE FIND",
                            "ORGANIZATION HACK",
                            "AMAZON ORGANIZER FAV",
                            "DESK SETUP EDIT",
                            "ACRYLIC STORAGE FAV",
                            "PANTRY STORAGE HACK",
                            "SMALL SPACE ORGANIZER",
                            "VIRAL STORAGE SOLUTION",
                            "AMAZON HOME HACK"
                        ]
                        headlines = [
                            "Aesthetic Storage That Looks Expensive",
                            "The Minimal Storage Upgrade Everyone Wants",
                            "Make Your Space Look Neat & Premium",
                            "Small Storage Upgrade Big Difference",
                            "Organization Finds You Will Actually Love",
                            "Declutter Your Space In Style",
                            "The Smart Storage Solution Everyone Is Buying",
                            "Viral Acrylic Organizer You Need"
                        ]
                        ctas = ["Shop storage on Amazon →", "Get organized today →", "Tap for shop link →", "Shop the organization edit →"]

                    # 8. PET DECOR
                    elif any(k in t_lower for k in ["pet", "cat", "dog", "scratcher", "litter box"]):
                        labels = ["AMAZON PET DECOR", "AESTHETIC PET FIND", "VIRAL PET FAV"]
                        headlines = ["Aesthetic Pet Decor That Fits Your Home", "Cute Pet Essentials Everyone Is Buying", "Make Your Pet Setup Look Premium"]
                        ctas = ["Shop pet find →", "Tap for Amazon link →", "Get the look →"]

                    # 9. HOLIDAY & SEASONAL
                    elif any(k in t_lower for k in ["pumpkin", "halloween", "christmas", "ghost", "wreath", "garland", "festive"]):
                        labels = ["SEASONAL DECOR FIND", "HOLIDAY HOME FAV", "COZY FALL EDIT", "CHRISTMAS HOME FIND"]
                        headlines = ["The Most Aesthetic Seasonal Decor Find", "Transform Your Home For The Holidays", "Viral Seasonal Decor Everyone Wants"]
                        ctas = ["Shop holiday decor →", "Get the seasonal look →", "Tap for Amazon link →"]

                    # 10. SECONDARY FALLBACK CHECK ON NICHE CONTEXT
                    elif any(k in n_lower for k in ["lamp", "light", "lighting"]):
                        labels = ["AMAZON LIGHTING FIND", "AESTHETIC ROOM GLOW"]
                        headlines = ["The Aesthetic Lighting Upgrade You Need", "This Lamp Changes The Whole Room Vibe"]
                        ctas = ["Shop this ambient find →", "Get the lighting look →"]
                    elif any(k in n_lower for k in ["bed", "bedroom", "pillow"]):
                        labels = ["AMAZON BEDROOM FIND", "COZY BEDDING EDIT"]
                        headlines = ["The Cozy Bedroom Upgrade Everyone Wants", "Transform Your Bed into A Cozy Haven"]
                        ctas = ["Shop bedroom finds →", "Get the cozy look →"]
                    elif any(k in n_lower for k in ["kitchen", "coffee"]):
                        labels = ["AMAZON KITCHEN FIND", "COFFEE BAR MUST-HAVE"]
                        headlines = ["Amazon's Favorite Kitchen Find", "The Cozy Kitchen Upgrade Everyone Wants"]
                        ctas = ["Shop the kitchen look →", "Tap for Amazon link →"]

                    # 11. GENERAL HOME DECOR (FINAL FALLBACK)
                    else:
                        labels = [
                            "AMAZON HOME FIND",
                            "COZY LIVING FAV",
                            "LUXURY HOME EDIT",
                            "AESTHETIC HOME FIND",
                            "AMAZON DECOR FAV",
                            "COZY HOME UPGRADE",
                            "WEST ELM STYLE DUPE"
                        ]
                        headlines = [
                            "The Cozy Home Upgrade Everyone Wants",
                            "Amazon's Favorite Home Decor Find",
                            "Aesthetic Home Decor That Looks Expensive",
                            "Small Home Upgrade Big Difference",
                            "Luxury Home Finds Under Budget",
                            "Make Your Home Look Like A Pinterest Board",
                            "Cozy Living Starts Here",
                            "The Best Amazon Home Decor Finds This Season"
                        ]
                        ctas = ["Shop the look →", "Get the look →", "See why everyone loves it →", "Tap to shop on Amazon →", "Discover the collection →"]

                    return random.choice(headlines), random.choice(labels), random.choice(ctas)

                curiosity_headline, category_label, cta_text = get_product_matched_overlay(
                    seo_data.title if seo_data and seo_data.title else product_details.title,
                    niche
                )

                pin_image_path = self.image_tools.create_pinterest_pin(
                    raw_image_path,
                    output_dir="images",
                    title_text=curiosity_headline,
                    category_label=category_label,
                    cta_text=cta_text
                )

            except Exception as e:
                logger.error(f"Failed to format Baddies Home Aesthetics Pin: {e}")
                past_products.append(selected_keyword)
                current_keyword = None
                continue
            
            # Board Selection
            suggested = seo_data.board.strip() if seo_data and seo_data.board else None
            target_board = self.choose_board_by_product(product_details.title, suggested)
                
            with self.db.connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as cnt FROM products WHERE board_name = ?", (target_board,))
                row = cursor.fetchone()
                count = row["cnt"] if row else 0
                
            if count >= 50:
                suffix = 2
                while True:
                    candidate_board = f"{target_board} {suffix}"
                    cursor = conn.execute("SELECT COUNT(*) as cnt FROM products WHERE board_name = ?", (candidate_board,))
                    row = cursor.fetchone()
                    candidate_count = row["cnt"] if row else 0
                    if candidate_count < 50:
                        target_board = candidate_board
                        break
                    suffix += 1
                    
            logger.info("Board chosen for this Pin: '%s' (current count: %d)", target_board, count)

            # Optimize Alt-Text & Pin Description
            logger.info("Optimizing Alt-Text & Description for Pinterest SEO & High CTR...")
            seo_data.alt_text = self.optimize_alt_text(seo_data.alt_text, target_board, niche)
            if "amazon" not in seo_data.description.lower() and "linktree" not in seo_data.description.lower():
                seo_data.description = f"{seo_data.description.strip()}\n\n🛒 Tap link to check current price & deals on Amazon via Linktree!"

            # Pre-publish Quality Check
            if not self.verify_quality(product_details, seo_data, pin_image_path, target_board):
                logger.warning("⚠️ Quality Check failed for candidate '%s'! Rejecting candidate and restarting research phase...", selected_keyword)
                past_products.append(selected_keyword)
                current_keyword = None
                continue

            # Step 5: Pinterest Upload
            async def step_pinterest_upload():
                logger.info("STEP 5: Uploading to Pinterest...")
                if not await self.pinterest.is_logged_in():
                    import os
                    email = os.getenv("PINTEREST_EMAIL")
                    password = os.getenv("PINTEREST_PASSWORD")
                    if not email or not password:
                        raise Exception("Pinterest credentials not found in settings/.env")
                        
                    await self.pinterest.login(email, password)
                    
                pin_url = await self.pinterest.create_pin(
                    image_path=pin_image_path,
                    title=seo_data.title,
                    description=seo_data.description,
                    board_name=target_board,
                    link=product_details.affiliate_url,
                    alt_text=seo_data.alt_text
                )
                if not pin_url:
                    raise Exception("Pinterest upload failed or did not return a valid URL.")
                return pin_url
                
            try:
                pin_url = await self.execute_task_with_memory("Pinterest Upload", step_pinterest_upload)
            except Exception as e:
                logger.error(f"Pinterest Upload failed: {e}")
                return False

            # Save to database immediately to prevent duplicates
            with self.db.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO products (product_name, category, board_name, status, image_path, source_url, title, description, affiliate_link, pin_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        selected_keyword,
                        niche,
                        target_board,
                        "Pinterest_Published",
                        pin_image_path,
                        product_details.image_url,
                        seo_data.title,
                        seo_data.description,
                        product_details.affiliate_url,
                        pin_url
                    )
                )

            # Step 6: Linktree Link Addition
            async def step_linktree_addition():
                logger.info("STEP 6: Adding affiliate link to Linktree Collection...")
                if not await self.linktree.is_logged_in():
                    logged_in = await self.linktree.login()
                    if not logged_in:
                        raise Exception("Failed to log in to Linktree via Google.")
                        
                success = await self.linktree.add_link_to_collection(
                    title=product_details.title,
                    url=product_details.affiliate_url,
                    collection_name=target_board
                )
                if not success:
                    raise Exception("Failed to add link to Linktree collection.")
                
            try:
                await self.execute_task_with_memory("Linktree Link Addition", step_linktree_addition)
                
                with self.db.connection() as conn:
                    conn.execute(
                        "UPDATE products SET status = 'Published' WHERE affiliate_link = ?",
                        (product_details.affiliate_url,)
                    )
            except Exception as e:
                logger.warning(f"⚠️ Linktree addition skipped ({e}). Pin was successfully published to Pinterest: {pin_url}")
                with self.db.connection() as conn:
                    conn.execute(
                        "UPDATE products SET status = 'Pinterest_Published' WHERE affiliate_link = ?",
                        (product_details.affiliate_url,)
                    )
            
            logger.info("🎉 SUCCESS! Pin published at: %s", pin_url)

            # Run Instant Link Audit Verification Check
            try:
                from utils.link_auditor import LinkAuditorBot
                bot = LinkAuditorBot(self.db)
                audit_res = bot.audit_single_product({
                    "id": 0,
                    "product_name": selected_keyword,
                    "title": product_details.title,
                    "board_name": target_board,
                    "affiliate_link": product_details.affiliate_url,
                    "pin_url": pin_url,
                    "status": "Published"
                })
                if audit_res.status == "Verified_Live":
                    logger.info("✅ Instant Link Audit: Pinterest & Linktree affiliate links verified live!")
                else:
                    logger.warning("⚠️ Instant Link Audit Alert: Status is '%s' (%s)", audit_res.status, ", ".join(audit_res.issues))
            except Exception as audit_err:
                logger.debug(f"Instant post-publish link audit notice: {audit_err}")

            return True

        logger.error("❌ Failed to find a unique, non-duplicate product after %d research attempts.", max_duplicate_retries)
        return False

    async def run_link_audit(self) -> list:
        """Run real-time link audit for all published products across Pinterest & Linktree."""
        from utils.link_auditor import LinkAuditorBot
        bot = LinkAuditorBot(self.db)
        return bot.audit_all_products()




    async def update_pin_analytics(self, scroll_count: int = 4) -> None:
        """
        Trigger Pinterest profile scraping and update the local database with impressions, clicks, saves.
        """
        logger.info("Triggering update_pin_analytics...")
        
        scraped_data = await self.pinterest.scrape_profile_analytics(scroll_count=scroll_count)
        if not scraped_data:
            logger.warning("No analytics data scraped or scraping failed.")
            return
            
        import datetime
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        
        updated_count = 0
        with self.db.connection() as conn:
            for item in scraped_data:
                pin_id = item["pin_id"]
                impressions = item["impressions"]
                saves = item["saves"]
                clicks = item["clicks"]
                
                cursor = conn.execute(
                    "UPDATE products SET impressions = ?, saves = ?, clicks = ?, stats_updated_at = ? WHERE pin_url LIKE ?",
                    (impressions, saves, clicks, now_str, f"%{pin_id}%")
                )
                if cursor.rowcount > 0:
                    updated_count += cursor.rowcount
                    logger.debug(f"Updated stats for pin ID {pin_id}: impressions={impressions}, saves={saves}, clicks={clicks}")
                    
        logger.info(f"update_pin_analytics complete. Updated database records for {updated_count} pins.")

    def parse_product_keyword(self, candidate: str) -> str:
        """
        Parses a potentially chatty, multi-line markdown response from Gemini 
        to extract exactly one clean home decor search query/product name.
        """
        candidate = candidate.strip().replace('"', "").replace("'", "")
        
        # Split by lines and remove empty ones
        lines = [line.strip() for line in candidate.split('\n') if line.strip()]
        if not lines:
            return "trending home decor product"
            
        # 1. Clean list prefixes, numbered items, and bold formatting
        for i in range(len(lines)):
            line = lines[i]
            line = line.replace("**", "")
            import re
            line = re.sub(r'^\s*[\-\*\•\d\.\)]+\s*', '', line).strip()
            lines[i] = line

        # 2. Try to locate standard plaintext search query blocks
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if "plaintext" in line_lower or "search query" in line_lower or "is:" in line_lower:
                if i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    if next_line and not next_line.startswith("#") and len(next_line) > 3:
                        # Ensure it doesn't contain blocklisted marketing words
                        if not any(w in next_line.lower() for w in ["pinterest", "google", "analysis", "trends", "passive income", "profits", "based on", "following"]):
                            return next_line
                        
        # 3. Known brand extraction from any line (even long sentences)
        known_brands = [
            "dyson", "shark", "omnilux", "dennis", "nuface", "braun", "foreo", "anua", "cosrx", 
            "joseon", "round lab", "centella", "tatcha", "paula", "glow recipe", "baccarat", 
            "sol de janeiro", "ysl", "black opium", "kayali", "replica", "good girl", "delina", 
            "west elm", "anthropologie", "cb2", "urban outfitters", "crate and barrel", 
            "merit", "huda", "milk makeup", "tower 28", "laneige", "bum bum", "tree hut", 
            "necessaire", "osea", "eos", "l'occitane", "lume", "olaplex", "k18", "gisou", 
            "mielle", "color wow", "ouai", "amika", "peter thomas", "shiseido", "roc", "cetaphil",
            "cerave", "la roche-posay", "ordinary", "inkey list", "kiss lash", "emi jay", "milani",
            "numbuzin", "rael", "kopari", "panoxyl", "loreal"
        ]
        
        for line in lines:
            line_lower = line.lower()
            for brand in known_brands:
                if brand in line_lower:
                    idx = line_lower.find(brand)
                    sub = line[idx:]
                    for char in [".", ",", ";", "\n", "  "]:
                        if char in sub:
                            sub = sub.split(char)[0]
                    sub = sub.strip()
                    if 5 < len(sub) < 120 and not any(w in sub.lower() for w in ["pinterest", "google", "analysis", "trends", "passive income", "profits"]):
                        return sub
                        
        # 4. Filter lines that don't contain blocklist words
        for line in lines:
            if len(line) < 90 and not line.startswith("#"):
                if not any(w in line.lower() for w in ["pinterest", "google", "analysis", "trends", "passive income", "profits", "based on", "following"]):
                    return line
                    
        # 5. Last resort fallback
        return "trending home decor product"
