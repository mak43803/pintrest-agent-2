"""
Settings - Typed application settings with environment variable loading.

Uses dataclasses and dotenv for configuration management.
All settings are validated at startup to fail fast on misconfiguration.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ── Project Paths ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
IMAGES_DIR = PROJECT_ROOT / "images"
DATABASE_DIR = PROJECT_ROOT / "database"


@dataclass(frozen=True)
class OllamaSettings:
    """Configuration for the Ollama LLM backend."""
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    timeout_seconds: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    stream: bool = True


@dataclass(frozen=True)
class BrowserSettings:
    """Configuration for the Playwright browser."""
    headless: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    slow_mo: int = int(os.getenv("BROWSER_SLOW_MO", "100"))
    viewport_width: int = int(os.getenv("BROWSER_VIEWPORT_WIDTH", "1280"))
    viewport_height: int = int(os.getenv("BROWSER_VIEWPORT_HEIGHT", "800"))
    user_agent: str | None = os.getenv("BROWSER_USER_AGENT", None)
    timeout_seconds: int = int(os.getenv("BROWSER_TIMEOUT", "30"))


@dataclass(frozen=True)
class DatabaseSettings:
    """Configuration for the SQLite database."""
    db_path: str = str(DATABASE_DIR / "pinterest_ai_agent.db")
    echo: bool = False
    journal_mode: str = "WAL"
    pool_size: int = 5
    busy_timeout_ms: int = 5000


@dataclass(frozen=True)
class AgentSettings:
    """Top-level agent configuration."""
    max_steps_per_task: int = 20
    retry_limit: int = 3
    action_delay_seconds: float = 1.5
    log_level: str = "INFO"
    debug_mode: bool = False


@dataclass(frozen=True)
class LinktreeSettings:
    """Configuration for Linktree automation."""
    username: str = os.getenv("LINKTREE_USERNAME", "BaddiesHomeAesthetics")
    password: str = os.getenv("LINKTREE_PASSWORD", "Minelazy1231@")
    profile_url: str = os.getenv("LINKTREE_URL", "https://linktr.ee/BaddiesHomeAesthetics")


@dataclass
class AppSettings:
    """
    Root application configuration.

    Aggregates all subsystem settings into a single access point.
    """
    agent: AgentSettings = field(default_factory=AgentSettings)
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    browser: BrowserSettings = field(default_factory=BrowserSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    linktree: LinktreeSettings = field(default_factory=LinktreeSettings)


# ── Singleton instance ─────────────────────────────────────────────────
_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """Return the global AppSettings singleton, creating it if needed."""
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings
