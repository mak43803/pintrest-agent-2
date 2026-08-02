"""
Pinterest AI Agent — Main Entry Point.
======================================

Runs the autonomous affiliate marketer continuously without daily limits or scheduled time restrictions.
Publishes pins with random intervals of 10 to 25 minutes.

RESUME SUPPORT:
- Agent state is tracked via SQLite DB (products table).
- On restart (e.g., power outage), it auto-detects how many pins were
  already posted today and resumes from where it left off.
- Waits for internet connectivity before starting.
- Can be added to Windows Startup for auto-launch on boot.
"""

import asyncio
import logging
import sys
import random
import datetime
import socket
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Force stdout/stderr to use UTF-8 to prevent charmap UnicodeEncodeErrors in Windows background tasks
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

from agent.pinterest_agent import PinterestAgent

# Setup local logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")
logger = logging.getLogger("pinterest_agent.main")


# ──────────────────────────────────────────────────────────────────────
# INTERNET CONNECTIVITY CHECK
# ──────────────────────────────────────────────────────────────────────

def is_internet_available() -> bool:
    """Check if internet is available by trying multiple DNS & HTTP servers."""
    test_targets = [
        ("8.8.8.8", 53),
        ("1.1.1.1", 53),
        ("www.google.com", 80),
        ("www.pinterest.com", 443)
    ]
    for host, port in test_targets:
        try:
            socket.create_connection((host, port), timeout=4)
            return True
        except OSError:
            continue
    return False



async def wait_for_internet(max_wait_minutes: int = 30) -> bool:
    """
    Wait until internet connectivity is restored.
    Checks every 10 seconds for up to max_wait_minutes.
    Returns True if internet came back, False if timed out.
    """
    if is_internet_available():
        return True

    logger.warning("⚡ No internet connection detected. Waiting for connectivity...")
    start = time.time()
    max_wait_seconds = max_wait_minutes * 60

    while time.time() - start < max_wait_seconds:
        await asyncio.sleep(10)
        if is_internet_available():
            logger.info("✅ Internet connection restored!")
            # Wait a few more seconds for network to stabilize
            await asyncio.sleep(5)
            return True
        elapsed = int(time.time() - start)
        if elapsed % 60 == 0:  # Log every minute
            logger.info(f"  Still waiting for internet... ({elapsed // 60} min elapsed)")

    logger.error(f"❌ No internet after {max_wait_minutes} minutes. Giving up.")
    return False


# ──────────────────────────────────────────────────────────────────────
# WINDOWS STARTUP SHORTCUT
# ──────────────────────────────────────────────────────────────────────

def setup_windows_startup():
    """
    Create a batch file in the Windows Startup folder so the agent
    auto-launches when the laptop turns on.
    """
    startup_folder = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    batch_file = startup_folder / "PinterestAIAgent.bat"
    
    project_dir = Path(__file__).parent.resolve()
    python_exe = sys.executable
    
    batch_content = f'''@echo off
title Pinterest AI Agent
cd /d "{project_dir}"
"{python_exe}" watchdog.py
pause
'''
    
    try:
        batch_file.write_text(batch_content, encoding="utf-8")
        logger.info(f"✅ Windows startup shortcut created: {batch_file}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create startup shortcut: {e}")
        return False


def remove_windows_startup():
    """Remove the Windows startup shortcut."""
    startup_folder = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    batch_file = startup_folder / "PinterestAIAgent.bat"
    
    if batch_file.exists():
        batch_file.unlink()
        logger.info("✅ Windows startup shortcut removed.")
        return True
    return False


# ──────────────────────────────────────────────────────────────────────
# ANALYTICS FEEDBACK LOOP CATEGORY SELECTION
# ──────────────────────────────────────────────────────────────────────

def get_next_category_based_on_analytics(db, categories: list[str]) -> str:
    """
    Select the next category using an Epsilon-Greedy approach with an Unposted Boost:
    - 40% chance: Choose from categories that have never been posted to guarantee coverage.
    - 45% chance: Exploitation (weighted by performance).
    - 15% chance: Uniform random exploration among all categories.
    """
    import random
    
    # Priority US, UK & Canada Viral Home Decor Bestsellers (60% Weight)
    viral_home_decor_priority = [
        "Aesthetic Sunset Projection Lamp",
        "Aesthetic Wavy Wall Mirror",
        "Mushroom Table Lamp",
        "Candle Warmer Lamp Vintage",
        "Chunky Knit Blanket Throw",
        "Bamboo Spice Jar Organizer Set",
        "Clear Acrylic Makeup & Skincare Vanity Organizer",
        "Amber Glass Soap Dispenser Bottle Set",
        "Donut Ceramic Vase for Pampas Grass",
        "Fairy String Curtain Lights",
        "Checkered Tufted Area Rug",
        "Flame Air Diffuser Essential Oil Humidifier",
        "Pure Washed Linen Duvet Cover Set",
        "Walnut Wood Floating Wall Shelves"
    ]

    if random.random() < 0.60:
        chosen_viral = random.choice(viral_home_decor_priority)
        logger.info("🏆 US/UK/CA Viral Home Decor Priority Mode: Selected '%s'", chosen_viral)
        return chosen_viral

    # Identify recent 10 posted categories to prevent immediate back-to-back repeats
    recent_posted = set()
    posted_cats = set()
    try:
        with db.connection() as conn:
            cursor = conn.execute("SELECT DISTINCT category FROM products WHERE status IN ('Published', 'Pinterest_Published')")
            for row in cursor.fetchall():
                posted_cats.add(row["category"].lower().strip())
                
            cursor_rec = conn.execute("SELECT category FROM products WHERE status IN ('Published', 'Pinterest_Published') ORDER BY created_at DESC LIMIT 10")
            for row in cursor_rec.fetchall():
                recent_posted.add(row["category"].lower().strip())
    except Exception as e:
        logger.debug(f"Failed to query posted categories: {e}")
        
    unposted_cats = [c for c in categories if c.lower().strip() not in posted_cats]
    
    # 1. 100% chance to boost unposted categories (forces fast-selling new items to post immediately)
    if unposted_cats:
        chosen = random.choice(unposted_cats)
        logger.info("Feedback Loop [Unposted Boost]: Selected unposted category: '%s'", chosen)
        return chosen

    # Filter out recent 10 categories to guarantee continuous non-repeating rotation
    available_categories = [c for c in categories if c.lower().strip() not in recent_posted]
    if not available_categories:
        available_categories = categories

    # 2. 20% chance of uniform random exploration
    if random.random() < 0.20:
        chosen = random.choice(available_categories)
        logger.info("Feedback Loop [Exploration]: Randomly selected category: '%s'", chosen)
        return chosen

    # 3. Exploitation (weighted by performance)
    category_scores = {cat: 1.0 for cat in categories} # Start with base score of 1.0 for all categories

    try:
        with db.connection() as conn:
            cursor = conn.execute(
                """
                SELECT category, SUM(impressions) as total_imp, SUM(clicks) as total_clicks, SUM(saves) as total_saves
                FROM products
                WHERE status IN ('Published', 'Pinterest_Published')
                GROUP BY category
                """
            )
            rows = cursor.fetchall()
            for row in rows:
                cat = row["category"]
                if cat in category_scores:
                    imp = row["total_imp"] or 0
                    clicks = row["total_clicks"] or 0
                    saves = row["total_saves"] or 0
                    # Weight calculation: Clicks (5.0) + Saves (2.0) + Impressions (0.1)
                    performance_weight = (clicks * 5.0) + (saves * 2.0) + (imp * 0.1)
                    category_scores[cat] += performance_weight
    except Exception as e:
        logger.error(f"Error calculating analytics weights: {e}. Falling back to random choice.")
        return random.choice(categories)

    # Weighted random selection
    total_score = sum(category_scores.values())
    choices = list(category_scores.keys())
    weights = [category_scores[c] / total_score for c in choices]
    
    chosen = random.choices(choices, weights=weights)[0]
    logger.info("Feedback Loop [Exploitation]: Selected category '%s' based on analytics (Weight: %.2f%%)", chosen, (category_scores[chosen]/total_score) * 100)
    return chosen


# ──────────────────────────────────────────────────────────────────────
# MAIN AGENT LOOP
# ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("🚀 Starting Pinterest AI Agent Continuous Loop...")
    
    # ── Wait for internet before anything ──
    if not await wait_for_internet(max_wait_minutes=30):
        print("❌ Cannot start without internet. Exiting.")
        return
    
    while True:
        agent = PinterestAgent()
        try:
            await agent.initialize()
            
            # ── Self-Healing Error Recovery Counters (Persistent across cycles) ──
            consecutive_failures = 0
            MAX_CONSECUTIVE_FAILURES = 5
            
            while True:
                # ── Periodic Analytics Sync (Every 24 hours) ──
                try:
                    last_sync_str = None
                    with agent.db.connection() as conn:
                        cursor = conn.execute("SELECT value FROM settings WHERE key = 'last_analytics_sync'")
                        row = cursor.fetchone()
                        if row:
                            last_sync_str = row["value"]
                            
                    should_sync = False
                    if not last_sync_str:
                        should_sync = True
                    else:
                        last_sync = datetime.datetime.fromisoformat(last_sync_str)
                        if datetime.datetime.now() - last_sync >= datetime.timedelta(hours=24):
                            should_sync = True
                            
                    if should_sync:
                        logger.info("🔄 Running daily Pinterest pin analytics sync...")
                        await agent.update_pin_analytics(scroll_count=4)
                        with agent.db.connection() as conn:
                            conn.execute(
                                "INSERT OR REPLACE INTO settings (key, value) VALUES ('last_analytics_sync', ?)",
                                (datetime.datetime.now().isoformat(),)
                            )
                except Exception as e:
                    logger.error(f"Periodic analytics sync failed: {e}")

                # ── Check internet before each cycle ──
                if not is_internet_available():
                    logger.warning("⚡ Internet lost! Waiting for reconnection...")
                    if not await wait_for_internet(max_wait_minutes=60):
                        logger.error("Internet not restored after 60 min. Stopping agent.")
                        break

                # 1. Count total pins published today and overall campaign progress (60-day target: 2,400 pins / 40 per day)
                with agent.db.connection() as conn:
                    cursor = conn.execute(
                        "SELECT COUNT(*) as cnt FROM products WHERE date(created_at) = date('now')"
                    )
                    row = cursor.fetchone()
                    today_count = row["cnt"] if row else 0
                    
                    cursor_total = conn.execute(
                        "SELECT COUNT(*) as cnt FROM products"
                    )
                    row_total = cursor_total.fetchone()
                    total_count = row_total["cnt"] if row_total else 0
                    
                TOTAL_CAMPAIGN_DAYS = 90
                logger.info("🚀 90-Day Non-Stop Campaign Progress: %d Pins published today | Total Campaign Pins: %d", today_count, total_count)
                    
                categories = [
                    # ── 🔥 TIER 1: FASTEST SELLERS (Impulse Buys Under $25) ──
                    # These are the #1 converting products on Pinterest right now
                    "LED strip lights for bedroom", "Sunset lamp aesthetic", "Mushroom table lamp",
                    "Candle warmer lamp vintage", "Chunky knit blanket throw", "Fairy string curtain lights",
                    "Minimalist line art prints set", "Floating wall shelves set", "Macrame wall hanging boho",
                    "Silk satin pillowcase set", "Aesthetic bubble candles set", "Faux eucalyptus garland",
                    "Ribbed fluted glass drinking set", "Decorative throw pillow covers boho",
                    "Woven storage basket set", "Star projector galaxy light", "Moon lamp 3D",
                    "Reed diffuser home fragrance", "Aesthetic quote posters wall art",
                    "Velvet non slip hangers set", "3D mirror wall stickers acrylic",
                    
                    # ── 💰 TIER 2: HIGH DEMAND KITCHEN & DINING ──
                    "Bamboo spice jar organizer set with labels", "Ceramic matcha whisk bowl set",
                    "Aesthetic ceramic mug set", "Wooden cutting board decorative",
                    "Linen cloth napkin set", "Nespresso pod holder acrylic", "Glass meal prep containers",
                    "Spice rack magnetic", "Fridge organization bins clear", "Coffee bar station setup",
                    "Espresso machine aesthetic", "Ribbed glassware set vintage",
                    "Fluted glass cups aesthetic", "Kitchen counter organizer",
                    
                    # ── 🛁 TIER 2: BATHROOM & SPA VIBES ──
                    "Bamboo bathtub tray caddy", "Aesthetic soap dispenser set amber glass",
                    "Eucalyptus shower bundle faux", "Gold brass towel hooks set",
                    "Marble vanity tray", "Aesthetic bathroom counter organizer",
                    "Bamboo over toilet storage shelf",
                    "Shower caddy aesthetic", "Bathroom organization aesthetic",
                    
                    # ── 🛏️ TIER 2: BEDROOM ESSENTIALS ──
                    "Linen duvet cover set neutral", "Tufted textured throw pillow",
                    "Sheer bed canopy drape", "Aesthetic alarm clock minimalist",
                    "Bedside table organizer", "Satin sheets aesthetic",
                    "Decorative pillow covers set", "Chunky cable knit blanket",
                    "Waffle weave blanket throw", "Faux fur luxury throw",
                    
                    # ── 🕯️ TIER 2: CANDLES & SCENT DECOR ──
                    "Twist spiral candle set aesthetic", "Soy wax scented candle gift set",
                    "Wax melt warmer ceramic", "Knot shaped decorative candle",
                    "Essential oil diffuser aesthetic", "Flameless LED candle set",
                    "Taper candle holders gold", "Candle holder set minimalist",
                    
                    # ── 🪞 TIER 2: MIRRORS & ACCENTS ──
                    "Wavy irregular wall mirror aesthetic", "Cloud shaped frameless mirror",
                    "Arched tabletop mirror", "Full length floor mirror gold",
                    "Ceramic donut vase set", "Cloud shaped ceramic vase",
                    "Aesthetic coffee table book set", "Terrazzo coaster set stone",
                    "Pampas grass arrangement tall", "Dried flower bouquet natural",
                    
                    # ── 🪑 TIER 2: DESK & OFFICE AESTHETIC ──
                    "Clear acrylic monitor stand", "Boucle ergonomic desk chair",
                    "Leather pastel desk mat", "Acrylic pen holder organizer",
                    "Desk cable management tray", "Aesthetic desk clock wood",
                    "Standing desk converter", "Monitor light bar", "Keyboard wrist rest",
                    
                    # ── 🛋️ TIER 2: RUGS & FLOOR DECOR ──
                    "Checkerboard area rug aesthetic", "Faux sheepskin fur rug white",
                    "Boho runner rug hallway", "Round jute braided rug",
                    "Washable kitchen runner rug", "Tufted bathroom mat cute",
                    
                    # ── 📦 TIER 2: ORGANIZATION & STORAGE ──
                    "Under sink sliding drawer organizer", "Clear acrylic desk organizer rotating",
                    "Stackable clear storage bins", "Over the door organizer hooks",
                    "Drawer dividers bamboo", "Cable management box", "Shoe storage rack aesthetic",
                    "Closet organizer system", "Jewelry stand organizer tree",
                    
                    # ── 🪴 TIER 2: SHELVES & DISPLAY ──
                    "Floating shelf set of 3 wood", "Picture ledge shelf long",
                    "Hexagonal geometric wall shelf", "Corner floating shelf set",
                    "Ladder bookshelf leaning", "Wall mounted book display",
                    
                    # ── 👑 2026 QUIET LUXURY & RICH NEUTRAL ESPRESSO/WALNUT TRENDS ──
                    "Walnut wood floating entryway console table", "Dark espresso ceramic coffee table tray",
                    "Boucle swivel accent chair neutral beige", "Deep chocolate brown throw pillow covers",
                    "Creamy caramel knitted throw blanket", "Wabi sabi ceramic footed bowl tray",
                    "Architectural arched display cabinet shelf", "Strawberry shaped ceramic flower vase aesthetic",
                    "Matte ceramic kitchen utensil crock holder", "PU leather storage box organizer set",
                    "Trompe l'oeil window wall art canvas print", "Carved raffia woven wall basket set",
                    
                    # ── 💻 WFH OFFICE & ERGONOMIC DESK AESTHETICS ──
                    "Under desk walking pad treadmill slim", "Laptop stand riser aluminum gold",
                    "Ergo chair lumbar support cushion aesthetic", "Desk pad leather blotter aesthetic",
                    "Headphone stand holder wood brass",
                    
                    # ── 🧺 LUXURY LAUNDRY ROOM & CLEANING AESTHETICS ──
                    "Glass laundry detergent dispenser bottle with tap", "Lint bin magnetic for dryer",
                    "Collapsible laundry hamper bamboo", "Wool dryer balls natural set of 6",
                    
                    # ── 🐾 PET HOME DECOR AESTHETICS (High Pinterest Female Impulse Buys) ──
                    "Aesthetic ceramic cat dog food bowl set", "Cute mushroom cat tree scratcher post",
                    "Washable dog bed aesthetic corduroy", "Hidden litter box enclosure furniture cabinet",
                    
                    # ── 🎃 HOLIDAY & FESTIVE SEASONAL DECOR ──
                    "Ceramic ghost Halloween night light", "Velvet pumpkin decor set pastel",
                    "Pre lit artificial Christmas garland mantle", "Bottlebrush mini Christmas trees set pastel",
                    
                    # ── 🥂 WEEKEND ENTERTAINING, SUNDAY RESET & DIY BEST-SELLERS ──
                    # Friday-Sunday peak buying: Hosting, Charcuterie, Sunday Spa Reset & Weekend DIY Room Projects!
                    "Bamboo charcuterie board set with cheese knives", "Coupe cocktail glass set vintage aesthetic",
                    "Tabletop indoor outdoor ethanol fire pit", "Bedside nightstand glass carafe and tumbler set",
                    "Aesthetic Sunday reset shower steamers set", "Aesthetic wine decanter with aerator",
                    "Peel and stick kitchen backsplash tile 3d", "Outdoor patio string lights heavy duty weatherproof",
                    "Aesthetic glass ice bucket with tongs", "Plush luxury hotel waffle bathrobe set",
                    "Under cabinet wireless LED strip lighting kit", "Cocktail shaker set gold brass with stand",
                    
                    # ── 🔮 2026 BREAKOUT PINTEREST TRENDS (Neo Deco, Afrohemian, Scalloped Jute & Botanicals) ──
                    "Scalloped jute area rug boho", "Faux olive tree in terracotta pot",
                    "Fluted brass wall sconce light set", "Footed marble bowl decor tray",
                    "Sculptural ceramic vase set textured", "Rechargeable wireless puck lights set",
                    "Berber pattern throw pillow cover", "Rattan woven pendant light fixture",
                    "Adire patterned hallway runner rug", "Realistic faux eucalyptus stems glass vase",
                    "Sky blue linen throw pillow cover", "Brass picture picture display light wireless",
                    "Decorative rattan storage box set", "Striped ceramic coffee mug set",
                    "Sculptural wine decanter aesthetic", "Burgundy ceramic vase accent",
                    
                    # ── ❄️ JANUARY BEST-SELLERS: NEW YEAR FRESH START, ORGANIZERS & CLEAN RESET ──
                    "Clear stackable fridge organization bins with handles", "Bamboo ziplock bag organizer for kitchen drawers",
                    "Under bed dustproof fabric closet storage bags", "Aesthetic daily habit and goal planning desk calendar",
                    "Bedroom air purifier HEPA aesthetic quiet", "Hygge wool felt storage baskets set UK Canada",
                    "Thermal blackout curtain panels velvet cold weather",

                    # ── 💖 FEBRUARY BEST-SELLERS: COZY ROMANTIC BEDROOM & VALENTINE AESTHETICS ──
                    "Diamond crystal touch rose bedside table lamp", "Red pink heart shaped plush velvet throw pillows",
                    "Luxury silk satin sheet and pillowcase set", "Aesthetic candle warmer lamp with dimmer timer",
                    "Heated electric throw blanket plush dual control", "Ceramic tea light candle warmer fondue set",

                    # ── 🌿 MARCH BEST-SELLERS: SPRING CLEANING, FRESH FLORALS & PASTEL ROOM REFRESH ──
                    "Faux real touch tulip stems in clear glass vase", "Pastel checkered throw pillow covers and linens",
                    "Floating wall bookshelves long picture ledge", "Aesthetic flower shaped plush cushion floor pillow",
                    "Woven rattan picnic and storage hamper UK Canada", "Pastel ceramic flower vase set decorative",

                    # ── 🐣 APRIL BEST-SELLERS: EASTER PASTEL TABLES, PATIO & BALCONY REFRESH ──
                    "Macrame boho hanging plant holders set of 4", "Scalloped woven table runner and linen napkins",
                    "Solar powered outdoor string lights for balcony patio", "Aesthetic pastel glassware goblet glass set",
                    "Terracotta herb planter pots indoor garden", "Solar outdoor garden lantern flickering flame",

                    # ── 🌸 MAY BEST-SELLERS: MOTHER'S DAY GIFTS, GARDEN PATIO & SUMMER PREP ──
                    "Luxury home fragrance reed diffuser gift set", "Aesthetic bamboo bathtub caddy tray organizer",
                    "Gold brass mirror tray for dresser perfume display", "Outdoor waterproof patio furniture cushion set",
                    "English garden floral cushion covers UK Canada", "Cast iron outdoor garden fire pit bowl",

                    # ── ☀️ JUNE BEST-SELLERS: SUMMER HOSTING, ICED COFFEE & PATIO ENTERTAINING ──
                    "Aesthetic glass milk carton pitcher and tumblers", "Iced coffee bar station accessories milk frother",
                    "HyperChiller instant beverage iced coffee cooler", "Aesthetic outdoor picnic blanket waterproof large",
                    "Ribbed glass water carafe set bedside nightstand", "Woven rattan sun lounger cushion pads",

                    # ── 🏖️ JULY BEST-SELLERS: MID-SUMMER REFRESH, OUTDOOR BBQ & SUNSET AESTHETICS ──
                    "Sunset projection lamp 16 colors with remote", "Solar mason jar firefly string lights outdoor",
                    "Tabletop ethanol fireplace bowl indoor outdoor", "Aesthetic snack bowl with built in straw holder",
                    "Northern Hygge outdoor candle lanterns UK Canada", "Citronella candle bowl outdoor patio bug repellant",

                    # ── 🍂 AUGUST BEST-SELLERS: DORM & EARLY FALL PREDICTIVE TOP BUYS ──
                    # August is the #1 month for College Dorm decor, Closet organization, and Early Fall transition!
                    "College dorm room organization aesthetic", "Under bed rolling storage containers clear",
                    "Aesthetic desk lamp with wireless charger", "Peel and stick floral arch wallpaper",
                    "Photo clip string fairy lights for bedroom", "Mini fridge stand with storage drawers",
                    "Fall pumpkin spice scented candle amber glass", "Terracotta burnt orange throw pillow covers",
                    "Chunky knit throw blanket caramel rust", "Autumn eucalyptus and dried wheat fall wreath",
                    "Solar mason jar string lights outdoor patio", "Closet vacuum storage bags space saver",
                    "Aesthetic ceramic cereal snack dispenser bin", "Over the door shoe organizer clear pockets",
                    "Collapsible fabric storage cubes set", "Faux ceramic pumpkin tabletop decor set",
                    "Earthy autumn linen table runner", "Flameless LED pillar candle set with remote",
                    "Cozy autumn fleece throw blanket burnt orange",
                    
                    # ── 🍂 SEPTEMBER BEST-SELLERS: AUTUMN RESET & PUMPKIN CHAI DECOR ──
                    "Checkered autumn fall doormat hey pumpkin", "Spiced apple cider amber jar candle",
                    "Aesthetic ceramic ghost and pumpkin mug set", "Harvest dining table runner linen rust",
                    "Chunky knit throw blanket terracotta cream", "Dried botanical fall centerpiece bouquet",
                    "Rustic wooden lantern set with LED candles",
                    
                    # ── 🎃 OCTOBER BEST-SELLERS: HALLOWEEN & COZY HYGGE PEAK (Highest CTR Month!) ──
                    "Floating candles with wand remote ceiling set", "Ceramic pastel pumpkin decor set tabletop",
                    "Ghost neon sign light spooky aesthetic", "Gothic dark academia velvet throw pillows",
                    "Pre lit Halloween witch hat porch lights", "Black flameless pillar candles set",
                    "Spooky season ghost bath mat cute", "Halloween front porch decor garland",
                    
                    # ── 🏷️ BLACK FRIDAY & CYBER MONDAY DEALS: HIGH-TICKET BIG COMMISSIONS (Late Nov Peak!) ──
                    # Black Friday is the #1 highest conversion rate week of the entire year for USA, UK & Canada!
                    "Dyson vacuum stand and accessory wall mount organizer", "Full length LED floor mirror with jewelry storage cabinet",
                    "Nespresso Vertuo espresso machine chrome aesthetic", "Robotic vacuum cleaner slim quiet for hardwood floors",
                    "KitchenAid stand mixer pastel retro edition", "Smart WiFi LED light strip sync with music bedroom",
                    "Electric tabletop fireplace heater flame effect", "Anti gravity water drop humidifier air purifier",
                    "Luxury silk pajama and bathrobe set 100 mulberry", "Electric towel warmer bucket for bathroom luxury spa",
                    "Electric wine opener gift set with foil cutter and pourer",
                    
                    # ── 🦃 NOVEMBER BEST-SELLERS: THANKSGIVING HARVEST & PRE-HOLIDAY GIFTING ──
                    "Thanksgiving harvest tableware dinner set", "Gold brass taper candle holder set of 3",
                    "Pre lit faux pine and eucalyptus mantle garland", "Luxury housewarming gift basket aesthetic",
                    "Sherpa fleece heated throw blanket electric", "Fireplace screen guard gold brass vintage",
                    "Earthy linen tablecloth natural beige", "Rustic ceramic gravy boat and serving platter",
                    
                    # ── 🎄 DECEMBER BEST-SELLERS: CHRISTMAS DECOR, HOLIDAY GIFTS & WINTER COZY (3x Sales Month!) ──
                    "Pastel mini bottlebrush Christmas tree set", "Faux fur Christmas stockings set emerald cream",
                    "Pre lit warm white birch tree indoor outdoor", "Velvet Christmas tree skirt emerald green gold",
                    "Nordic wooden star window hanging lights", "Holiday luxury candle gift box set",
                    "Winter wonderland snow globe aesthetic", "Christmas mantle stocking hooks set gold brass",
                    "Holiday fragrance reed diffuser gift set", "Fleece plaid holiday throw blanket cozy",
                    
                    # ── 🌿 TIER 3: SEASONAL (Aug-Oct Money Makers) ──
                    "Fall autumn wreath front door", "Artificial pumpkin decor set",
                    "Linen table runner natural", "Fall throw pillow covers",
                    "Autumn candle set pumpkin spice", "Harvest centerpiece decor",
                    
                    # ── 🔥 TIER 3: VIRAL TIKTOK & PINTEREST DUPES ──
                    "Anthropologie mirror dupe gold", "West Elm vase dupe ceramic",
                    "Mushroom shaped decorative lamp", "Rattan boho pendant light",
                    "Boucle accent chair", "Japandi style bedroom decor",
                    "Cottagecore room aesthetic", "Coquette room decor bow",
                    "Danish pastel room decor", "Coastal cowgirl home decor",
                    "Old money room aesthetic", "Dark academia room decor",
                    
                    # ── 💎 TIER 4: HIGH TICKET ITEMS ($30-$150) = BIG COMMISSIONS ──
                    # These products give $1.50-$6.00 commission per sale!
                    "Full length floor mirror with lights", "LED mirror Hollywood style",
                    "Velvet blackout curtains set", "Linen curtain panels natural",
                    "Queen comforter set aesthetic boho", "Duvet cover set king linen",
                    "Weighted blanket aesthetic 15lb", "Sherpa fleece blanket oversized",
                    "Bar cart gold rolling", "Accent side table round marble",
                    "Bookshelf 5 tier industrial", "TV stand mid century modern",
                    "Boucle dining chairs set of 2", "Velvet accent chair living room",
                    "Area rug 5x7 boho washable", "Shag rug white fluffy living room",
                    "Electric wax warmer with wax melts bundle", "Essential oil diffuser set with oils",
                    "Air purifier bedroom aesthetic", "Humidifier large room aesthetic",
                    "Keurig coffee maker mini aesthetic", "Electric kettle gooseneck",
                    "Stand mixer pastel retro", "Toaster retro aesthetic",
                    "Writing desk with drawers aesthetic", "Minimalist study desk set",
                    "Closet organizer system hanging", "Shoe rack tower 10 tier",
                    "Towel warmer bucket bathroom", "Electric fireplace tabletop",
                    "Smart LED bulbs color changing set", "Projector mini portable HD",
                    "Bluetooth speaker aesthetic vintage", "Record player turntable vintage",
                    "Desk lamp LED wireless charging", "Ring light with tripod stand",
                    
                    # ── 🎁 GOLDEN COMBO: GIFT SETS & BUNDLES (Highest Cart Value) ──
                    # People who buy gifts add MORE items to cart = bigger commission!
                    "Home decor gift set luxury", "Housewarming gift basket aesthetic",
                    "Housewarming gift set aesthetic", "New home gift box women",
                    "Candle gift set luxury soy wax", "Candle and diffuser gift set",
                    "Kitchen gift set aesthetic", "Coffee lover gift set aesthetic",
                    "Cozy night in gift box blanket candle", "Home fragrance gift set reed diffuser",

                    # ── 👑 TOP US/UK WOMEN IMPULSE BUYS (100% Home Decor & Aesthetic Living Finds) ──
                    "Glass tumbler with bamboo lid and straw", "Electric candle lighter rechargeable",
                    "Handheld milk frother for coffee matcha", "Travel jewelry box organizer mini",
                    "Aesthetic tissue box cover holder", "Amber glass soap dispenser set with tray",
                    "Ceramic pen holder desk cup", "Golden brass mirror tray for dresser",
                    "Wearable blanket hoodie oversized", "Cold brew coffee maker pitcher glass",
                    "Crystal touch lamp diamond rose light", "Motion sensor LED night light strip",
                    "Woven cotton rope storage basket", "Bedside table lamp with USB port",
                    "Aesthetic ribbed glass vase set",

                    # ── 🦄 ULTRA-UNIQUE & VIRAL IMPULSE BUYS (US, UK & Canada Female Favorites) ──
                    # These unique visual items convert at 3x higher rates when scrolled on Pinterest feed!
                    "Flame air diffuser humidifier candle effect", "Book shaped flower vase acrylic clear",
                    "Super absorbent diatomite stone bath mat", "Levitating magnetic moon lamp floating",
                    "Flower shaped plush throw pillow coquette", "Cloud shaped magnetic key holder for wall",
                    "Retro TV shaped tissue box holder phone stand", "Glass milk carton pitcher aesthetic",
                    "Melting clock Salvador Dali shelf decor", "Aesthetic book nook shelf insert LED diorama",
                    "Cat claw shaped door stopper silicone", "Automatic pan stirrer with timer",

                    # ── ✨ LUXURY & AESTHETIC HOME ACCENTS (High Pinterest Conversion) ──
                    "Astronaut galaxy star projector light", "Nordic minimalist mushroom cordless table lamp",
                    "Tulip night light DIY mirror cube", "Himalayan pink salt lamp touch dimmer",
                    "Electric wine opener gift set with aerator", "Vintage embossed glassware goblet cups set",
                    "Rotating lazy susan organizer bamboo", "Wall mounted waterproof phone case for shower",
                    "Gold stainless steel measuring spoons set", "Decorative ceramic knot ornament sculpture",
                    "Aesthetic arch bookend set heavy book holder", "Electric heated throw blanket plush",

                    # ── ⚡ INSTANT BUY & PROBLEM SOLVER WINNERS (US, UK & Canada Women Favorites) ──
                    # These "Instant Dopamine & Problem Solver" items have the highest 1-click Amazon conversion rates!
                    "HyperChiller instant iced coffee cooler beverage", "Electric spin scrubber bathroom cordless cleaner",
                    "Bagel slicer guillotine cutter safety stand", "Cordless heating pad belt for cramps massage",
                    "Silicone stove counter gap cover set", "Herb shears 5 blade scissors cleaning comb",
                    "Magnetic measuring spoons set dual sided stainless", "Mini bag sealer heat sealer for chips snacks",
                    "Touchless motion sensor mini trash can vanity", "Ergonomic under desk footrest pillow memory foam",
                    "Self squeezing sponge mop mini", "Aesthetic snack bowl with built in straw",

                    # ── 🍳 VIRAL TIKTOK KITCHEN & COFFEE MUST-HAVES (Top Amazon Conversion) ──
                    "Electric salt and pepper grinder set gravity automatic", "Olive oil dispenser bottle with silicone brush drip free",
                    "Over the sink roll up dish drying rack stainless steel", "Vegetable chopper slicer dicer 12 in 1 container",
                    "Under cabinet magnetic knife strip holder gold brass", "Clear acrylic magnetic fridge calendar weekly planner",
                    "Bamboo ziplock bag organizer for kitchen drawer", "Silicone utensil rest with drip pad for stove top",
                    "Aesthetic glass oil and vinegar dispenser set with tray", "Electric garlic chopper mini cordless food processor",
                    "Ice cube tray with bin and press plate lid container", "Aesthetic matcha whisk set ceramic bowl bamboo chasen",
                    "Espresso dosing funnel and wdt distributor tool set", "Under sink organizer 2 tier pull out sliding drawer",

                    # ── 🚿 LUXURY BATHROOM & VANITY AESTHETICS (High Female CTR on US Pinterest) ──
                    "Smart anti fog LED bathroom mirror dimmable", "Gold brass towel hook set wall mount aesthetic",
                    "Luxury hotel waffle weave bath towel set 100 organic cotton", "Aesthetic ceramic toothbrush holder dispenser set",
                    "Clear acrylic makeup organizer drawers vanity storage", "Aesthetic bath mat plush check pattern non slip",

                    # ── 🌸 COZY BEDROOM & DESK MOOD ELEVATORS (Impulse Dopamine Buys) ──
                    "Pebble shaped cordless table lamp touch control", "Cloud aesthetic ceiling light flush mount fixture",
                    "Faux leather desk pad blotter aesthetic dual sided", "Pastel retro mechanical wireless keyboard bluetooth",
                    "Aesthetic velvet hanger set gold swivel hook", "Stackable clear acrylic shoe display box set"
                ]

                # ── Real-Time Viral Trend Bypass Check (Every 3 hours) ──
                trending_product = None
                trending_category = None
                try:
                    last_trend_check_str = None
                    with agent.db.connection() as conn:
                        cursor = conn.execute("SELECT value FROM settings WHERE key = 'last_trend_check'")
                        row = cursor.fetchone()
                        if row:
                            last_trend_check_str = row["value"]
                            
                    should_check_trends = False
                    if not last_trend_check_str:
                        should_check_trends = True
                    else:
                        last_check = datetime.datetime.fromisoformat(last_trend_check_str)
                        if datetime.datetime.now() - last_check >= datetime.timedelta(hours=3):
                            should_check_trends = True
                            
                    if should_check_trends:
                        logger.info("⚡ Checking Google and Pinterest Trends for real-time viral home decor products...")
                        
                        p_trends = await agent.pinterest.get_us_home_decor_trends()
                        g_trends = await agent.pinterest.get_google_home_decor_trends()
                        combined_trends = f"{p_trends}, {g_trends}"
                        
                        trend_data = await agent.gemini.detect_viral_trend_bypass(combined_trends, categories)
                        
                        with agent.db.connection() as conn:
                            conn.execute(
                                "INSERT OR REPLACE INTO settings (key, value) VALUES ('last_trend_check', ?)",
                                (datetime.datetime.now().isoformat(),)
                            )
                            
                        if trend_data and trend_data.get("trend_detected"):
                            raw_keyword = trend_data["product_keyword"]
                            prod_keyword = agent.parse_product_keyword(raw_keyword)
                            
                            # Validate keyword contains no blocked terms and is not generic
                            prod_lower = prod_keyword.lower()
                            blocked_terms = ["pinterest", "google", "analysis", "trends", "passive income", "profits"]
                            is_generic = prod_lower in ["trending home decor product", "home decor find"] or len(prod_keyword) < 4
                            has_blocked = any(w in prod_lower for w in blocked_terms)
                            
                            if is_generic or has_blocked:
                                logger.warning("Bypass trend keyword contains blocked/generic terms: '%s'. Skipping bypass.", prod_keyword)
                            else:
                                # Double check if we already posted it
                                with agent.db.connection() as conn:
                                    chk = conn.execute("SELECT 1 FROM products WHERE LOWER(product_name) = LOWER(?)", (prod_keyword,))
                                    if not chk.fetchone():
                                        trending_product = prod_keyword
                                        trending_category = trend_data["category"]
                                        logger.info("🔥 VIRAL TREND DETECTED: '%s' in category '%s'. Bypassing normal schedule!", trending_product, trending_category)
                                    else:
                                        logger.info("Detected trend '%s' but it was already posted. Skipping bypass.", prod_keyword)
                except Exception as e:
                    logger.error(f"Error checking real-time trends bypass: {e}")

                # 2. Determine the category & product for this cycle
                if trending_product and trending_category:
                    current_category = trending_category
                    logger.info("Executing Pipeline Cycle #%d in Bypass Mode for Trending Product: '%s'...", today_count + 1, trending_product)
                else:
                    current_category = get_next_category_based_on_analytics(agent.db, categories)
                    logger.info("Executing Pipeline Cycle #%d for Category: '%s'...", today_count + 1, current_category)
                
                # ── 🧹 6-MONTH CONTINUOUS AUTOPILOT MAINTENANCE (Every 30 cycles) ──
                if today_count > 0 and today_count % 30 == 0:
                    try:
                        logger.info("🧹 Running 6-Month Maintenance: Cleaning RAM & truncating log files...")
                        # 1. Truncate heavy log file if over 15MB
                        log_file = Path("pinterest_agent.log")
                        if log_file.exists() and log_file.stat().st_size > 15 * 1024 * 1024:
                            log_file.write_text("=== Log file truncated for 6-Month Maintenance ===\n", encoding="utf-8")
                            logger.info("✅ Log file truncated cleanly.")
                            
                        # 2. Restart browser instance to release Chromium RAM memory leaks
                        await agent.browser_manager.close()
                        await asyncio.sleep(3)
                        await agent.browser_manager.initialize()
                        logger.info("✅ Browser RAM refreshed successfully.")
                    except Exception as clean_err:
                        logger.debug(f"Maintenance task skipped: {clean_err}")

                # ── Run pipeline with self-healing ──
                try:
                    success = await agent.run_affiliate_pipeline(niche=current_category, product_keyword=trending_product)
                    consecutive_failures = 0  # Reset on success
                except Exception as e:
                    consecutive_failures += 1
                    error_str = str(e).lower()
                    logger.error(f"Pipeline error (failure #{consecutive_failures}): {e}")
                    success = False
    
                    # ── Detect error type and self-heal ───────────────────────────
                    is_browser_crash = any(kw in error_str for kw in [
                        "playwright", "browser", "page", "context", "crashed",
                        "target closed", "connection refused", "websocket"
                    ])
                    is_network_error = any(kw in error_str for kw in [
                        "timeout", "network", "dns", "connection", "timed out", "net::"
                    ])
    
                    if is_browser_crash:
                        logger.warning("🔧 Browser crash detected! Attempting browser restart...")
                        try:
                            await agent.browser_manager.close()
                            await asyncio.sleep(5)
                            await agent.browser_manager.initialize()
                            logger.info("✅ Browser restarted successfully!")
                        except Exception as restart_err:
                            logger.error(f"Browser restart failed: {restart_err}. Reinitializing full agent...")
                            try:
                                await agent.shutdown()
                            except Exception:
                                pass
                            agent = PinterestAgent()
                            await agent.initialize()
                            logger.info("✅ Full agent reinitialized!")
    
                    elif is_network_error:
                        logger.warning("🌐 Network error detected! Waiting for connection...")
                        await wait_for_internet(max_wait_minutes=15)
    
                    # ── Exponential backoff based on failure count ─────────────────
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        logger.error(f"⚠️ {MAX_CONSECUTIVE_FAILURES} consecutive failures! Sleeping 30 min before retry...")
                        await asyncio.sleep(1800)  # 30 minutes
                        consecutive_failures = 0
                    elif consecutive_failures >= 3:
                        logger.warning("3 failures in a row. Sleeping 15 min...")
                        await asyncio.sleep(900)  # 15 minutes
                    else:
                        logger.warning("Retrying in 5 minutes...")
                        await asyncio.sleep(300)  # 5 minutes
                    continue
    
                # ── Handle success / duplicate after try block ─────────────────
                if success == "DUPLICATE":
                    logger.warning("Duplicate detected. Retrying cycle immediately with next category...")
                    continue
                elif success:
                    logger.info("✅ Pin cycle completed successfully.")
                else:
                    logger.error("Pipeline returned False. Retrying in 5 minutes...")
                    await asyncio.sleep(300)
                    continue
                    
                # 3. Safe Zone Human Pacing: Random 20 to 30 minutes delay between pins (Non-stop for 90 Days)
                import random
                interval_mins = random.randint(20, 30)
                logger.info("✅ Safe Zone Pacing: Next pin scheduled in %d minutes [90-Day Non-Stop Campaign]...", interval_mins)
                await asyncio.sleep(interval_mins * 60)
                
            # Exit outer loop cleanly if inner loop breaks without Exception
            break
            
        except KeyboardInterrupt:
            print("\n⚠️ Agent stopped by user.")
            break
        except Exception as e:
            logger.error(f"\n🔥 Fatal Error in scheduler: {e}. Restarting in 60 seconds...")
            await asyncio.sleep(60)
            logger.info("♻️ Auto-restarting main loop after fatal error...")
            continue
        finally:
            try:
                await agent.shutdown()
            except Exception:
                pass
            print("🛑 Agent shutdown cycle complete.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Handle --setup-startup and --remove-startup flags
    if "--setup-startup" in sys.argv:
        setup_windows_startup()
        print("Agent will now auto-start when your laptop turns on!")
        sys.exit(0)
    elif "--remove-startup" in sys.argv:
        remove_windows_startup()
        print("Agent auto-start removed.")
        sys.exit(0)
    
    asyncio.run(main())
