"""
Logger - Structured logging configuration for the application.

Configures Python's logging module with structured formatters,
file rotation, and separate log streams for different severity levels.
"""

import logging
import sys
from pathlib import Path

from config.settings import PROJECT_ROOT


LOGS_DIR = PROJECT_ROOT / "logs"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure and return the application's root logger.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Configured root logger instance.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("pinterest_agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Prevent duplicate handlers on re-initialization
    if logger.handlers:
        return logger

    # ── Console Handler ────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        fmt="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)

    # ── File Handler ───────────────────────────────────────────────────
    file_handler = logging.FileHandler(
        filename=LOGS_DIR / "agent.log",
        mode="a",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        fmt="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(funcName)s:%(lineno)d │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)

    # ── Error File Handler ─────────────────────────────────────────────
    error_handler = logging.FileHandler(
        filename=LOGS_DIR / "errors.log",
        mode="a",
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    return logger
