"""
Helpers - General-purpose utility functions.

Small, stateless helper functions used across the application.
"""

import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use as a safe filename.

    Args:
        name: Raw string to sanitize.

    Returns:
        Filesystem-safe filename string.
    """
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)
    sanitized = sanitized.strip(". ")
    return sanitized[:200]  # Limit length


def generate_timestamp_id() -> str:
    """Generate a unique timestamp-based identifier."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d_%H%M%S_%f")


def hash_string(text: str) -> str:
    """Generate a SHA-256 hash of the input string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_directory(path: Path) -> Path:
    """Create directory (and parents) if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max_length, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
