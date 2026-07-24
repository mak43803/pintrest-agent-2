"""
config.py — Root-level configuration loader.

Convenience module that loads environment variables from .env
and re-exports the settings singleton for easy imports:

    from config import settings
"""

from pathlib import Path

from dotenv import load_dotenv

# ── Load .env file ─────────────────────────────────────────────────────
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

# ── Re-export settings ─────────────────────────────────────────────────
from config.settings import get_settings, AppSettings  # noqa: E402, F401

settings: AppSettings = get_settings()
