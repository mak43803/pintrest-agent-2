"""
Models — Data models and enumerations for the database layer.
==============================================================

Defines all table schemas as Python dataclasses and the Status
enumeration used across multiple tables. Each model maps 1:1 to
a SQLite table and provides factory methods for row-to-object
conversion.

Design:
    - Frozen dataclasses for immutability after creation
    - Optional fields use ``None`` defaults for nullable columns
    - ``from_row()`` class methods convert raw SQLite rows to typed objects
    - ``to_dict()`` methods enable clean serialization

Tables:
    - Product  → ``products``
    - Task     → ``tasks``
    - LogEntry → ``logs``
    - Setting  → ``settings``
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════
# Status Enumeration
# ═══════════════════════════════════════════════════════════════════════

class Status(str, Enum):
    """
    Lifecycle status for products and tasks.

    Inherits from ``str`` so that enum values serialize directly
    into SQLite TEXT columns without manual ``.value`` calls.
    """
    PENDING   = "Pending"
    RUNNING   = "Running"
    COMPLETED = "Completed"
    FAILED    = "Failed"
    SKIPPED   = "Skipped"

    def __str__(self) -> str:
        return self.value


# ═══════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════

def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════════════════
# Product Model  →  ``products`` table
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Product:
    """
    Represents a Pinterest product to be pinned.

    Attributes:
        id:              Auto-incremented primary key.
        product_name:    Name of the product.
        category:        Product category for board routing.
        board_name:      Target Pinterest board name.
        status:          Current processing status.
        image_path:      Local filesystem path to the product image.
        source_url:      Original URL (e.g., raw Amazon product URL).
        title:           Generated pin title.
        description:     Generated pin description.
        affiliate_link:  Affiliate/referral URL for the product.
        retry_count:     Number of failed processing attempts.
        created_at:      Row creation timestamp (UTC ISO-8601).
        updated_at:      Last modification timestamp (UTC ISO-8601).
    """
    product_name: str
    category: str
    board_name: str
    status: str = Status.PENDING.value
    image_path: str | None = None
    source_url: str | None = None
    title: str | None = None
    description: str | None = None
    affiliate_link: str | None = None
    retry_count: int = 0
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    pin_url: str | None = None
    impressions: int = 0
    clicks: int = 0
    saves: int = 0
    stats_updated_at: str | None = None
    id: int | None = None

    # ── Factories ──────────────────────────────────────────────────────

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Product:
        """
        Construct a Product from a SQLite Row dictionary.

        Args:
            row: A ``sqlite3.Row`` cast to dict or accessed by key.

        Returns:
            A fully-populated Product instance.
        """
        row_dict = dict(row)
        return cls(
            id=row_dict.get("id"),
            product_name=row_dict["product_name"],
            category=row_dict["category"],
            board_name=row_dict["board_name"],
            status=row_dict["status"],
            image_path=row_dict.get("image_path"),
            source_url=row_dict.get("source_url"),
            title=row_dict.get("title"),
            description=row_dict.get("description"),
            affiliate_link=row_dict.get("affiliate_link"),
            retry_count=row_dict.get("retry_count", 0),
            created_at=row_dict["created_at"],
            updated_at=row_dict["updated_at"],
            pin_url=row_dict.get("pin_url"),
            impressions=row_dict.get("impressions", 0),
            clicks=row_dict.get("clicks", 0),
            saves=row_dict.get("saves", 0),
            stats_updated_at=row_dict.get("stats_updated_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the model to a plain dictionary."""
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# Task Model  →  ``tasks`` table
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Task:
    """
    Represents a tracked agent task.

    Attributes:
        id:           Auto-incremented primary key.
        task_name:    Human-readable task identifier.
        current_step: The step the task is currently on.
        status:       Current lifecycle status.
        started_at:   Timestamp when the task began.
        finished_at:  Timestamp when the task completed (or failed).
        last_error:   Most recent error message, if any.
    """
    task_name: str
    current_step: str = ""
    status: str = Status.PENDING.value
    started_at: str = field(default_factory=_utc_now)
    finished_at: str | None = None
    last_error: str | None = None
    id: int | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Task:
        """Construct a Task from a SQLite Row dictionary."""
        return cls(
            id=row["id"],
            task_name=row["task_name"],
            current_step=row["current_step"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            last_error=row["last_error"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the model to a plain dictionary."""
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# LogEntry Model  →  ``logs`` table
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class LogEntry:
    """
    Represents a persisted log record.

    Attributes:
        id:         Auto-incremented primary key.
        level:      Log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        message:    Log message content.
        module:     Source module that generated the log.
        created_at: Timestamp of the log entry.
    """
    level: str
    message: str
    module: str = ""
    created_at: str = field(default_factory=_utc_now)
    id: int | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> LogEntry:
        """Construct a LogEntry from a SQLite Row dictionary."""
        return cls(
            id=row["id"],
            level=row["level"],
            message=row["message"],
            module=row["module"],
            created_at=row["created_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the model to a plain dictionary."""
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# Setting Model  →  ``settings`` table
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Setting:
    """
    Represents a key-value configuration setting.

    The ``key`` column is the PRIMARY KEY (no auto-increment id).

    Attributes:
        key:   Unique setting identifier.
        value: Setting value stored as TEXT.
    """
    key: str
    value: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Setting:
        """Construct a Setting from a SQLite Row dictionary."""
        return cls(
            key=row["key"],
            value=row["value"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the model to a plain dictionary."""
        return asdict(self)
