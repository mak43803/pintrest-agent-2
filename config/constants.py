"""
Constants — Application-wide constants and default values for Pinterest AI Agent V5.0.
"""

# ── Application Metadata ──────────────────────────────────────────────
APP_NAME = "Pinterest AI Agent"
APP_VERSION = "5.0.0"
APP_DESCRIPTION = "Elite Autonomous AI Agent for Pinterest Home Decor Affiliate Growth (US, UK, CA, AU)"

# ── Pinterest URLs ─────────────────────────────────────────────────────
PINTEREST_BASE_URL = "https://www.pinterest.com"
PINTEREST_LOGIN_URL = "https://www.pinterest.com/login/"
PINTEREST_SEARCH_URL = "https://www.pinterest.com/search/pins/?q={query}"
PINTEREST_PROFILE_URL = "https://www.pinterest.com/{username}/"
PINTEREST_TRENDS_URL = "https://trends.pinterest.com"

# ── Target Market & Demographics ──────────────────────────────────────
TARGET_MARKETS = ["USA", "Canada", "United Kingdom", "Australia"]
TARGET_AGE_RANGE = "24-55"
TARGET_GENDER_RATIO = "70-90% Female"

# ── Seasonal Content Calendar ──────────────────────────────────────────
SEASONAL_CALENDAR = {
    1: "Organization & New Year Reset",
    2: "Valentine's Decor & Romantic Touches",
    3: "Spring Decor & Refresh",
    4: "Outdoor & Patio Prep",
    5: "Mother's Day & Living Room Aesthetics",
    6: "Summer Entertaining & Glassware",
    7: "Patio & Ambient Outdoor Lighting",
    8: "Back to School & Dorm Storage",
    9: "Fall Decor & Autumn Cozy Aesthetics",
    10: "Halloween Decor & Spooky Chic",
    11: "Thanksgiving & Holiday Dining",
    12: "Christmas & Holiday Gift Guides"
}

# ── Rate Limiting ──────────────────────────────────────────────────────
MIN_ACTION_DELAY_SECONDS = 1.0
MAX_ACTION_DELAY_SECONDS = 5.0
MAX_REQUESTS_PER_MINUTE = 30

# ── File Extensions ────────────────────────────────────────────────────
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# ── Database ───────────────────────────────────────────────────────────
DB_FILENAME = "pinterest_ai_agent.db"
MAX_CONVERSATION_HISTORY = 100
MAX_MEMORY_ENTRIES = 10000

# ── LLM ────────────────────────────────────────────────────────────────
DEFAULT_CONTEXT_WINDOW = 8192
MAX_RETRIES_ON_PARSE_FAILURE = 3
