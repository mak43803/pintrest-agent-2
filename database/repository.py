"""
Repository — Data access layer implementing the Repository Pattern.
====================================================================

Encapsulates all SQL operations behind clean Python methods so that
no other module in the application needs to write raw SQL. Every
method uses parameterized queries to prevent SQL injection, operates
within a transaction (auto-commit on success, rollback on error),
and logs its actions for observability.

Public API Summary:

    Products
    ────────
    insert_product(...)           → int           Insert a new product row.
    get_next_pending_product()    → Product|None   Fetch the oldest pending product.
    update_status(id, status)     → None          Change a product's status.
    update_image_path(id, path)   → None          Set the image path.
    update_title(id, title)       → None          Set the generated title.
    update_description(id, desc)  → None          Set the generated description.
    update_affiliate_link(id, url)→ None          Set the affiliate link.
    increase_retry(id)            → None          Increment the retry counter.

    Logs
    ────
    save_log(level, message, ...)→ None           Persist a log entry.
    get_logs(limit, level)       → list[LogEntry] Query persisted logs.

    Settings
    ────────
    save_setting(key, value)     → None           Upsert a setting.
    get_setting(key)             → str|None        Read a setting value.
"""

from __future__ import annotations

import logging
from typing import Optional

from database.database import Database
from database.models import LogEntry, Product, Setting, Status

logger = logging.getLogger("pinterest_agent.database.repository")


class Repository:
    """
    Unified data-access repository for all database entities.

    Follows the Repository Pattern: every public method maps to a
    single, well-defined data operation. The underlying ``Database``
    instance is injected via the constructor (Dependency Injection),
    making the repository trivially testable with a mock or in-memory DB.

    Args:
        db: An initialized and connected ``Database`` instance.
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(self, db: Database) -> None:
        self._db = db
        logger.debug("Repository initialized with database: %s", db)

    # ═══════════════════════════════════════════════════════════════════
    #  PRODUCTS
    # ═══════════════════════════════════════════════════════════════════

    def insert_product(
        self,
        product_name: str,
        category: str = "",
        board_name: str = "",
        status: str = Status.PENDING.value,
        image_path: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        affiliate_link: Optional[str] = None,
    ) -> int:
        """
        Insert a new product into the ``products`` table.

        Args:
            product_name:   Name of the product (required).
            category:       Product category for board routing.
            board_name:     Target Pinterest board.
            status:         Initial status (default ``Pending``).
            image_path:     Path to the product image.
            title:          Pin title.
            description:    Pin description.
            affiliate_link: Affiliate/referral URL.

        Returns:
            The auto-generated ``id`` of the inserted row.

        Raises:
            DatabaseQueryError: If the insert fails.
        """
        sql = """
            INSERT INTO products
                (product_name, category, board_name, status,
                 image_path, title, description, affiliate_link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            product_name,
            category,
            board_name,
            status,
            image_path,
            title,
            description,
            affiliate_link,
        )

        cursor = self._db.execute(sql, params)
        row_id = cursor.lastrowid

        logger.info(
            "Product inserted  │  id=%d  name=%s  status=%s",
            row_id,
            product_name,
            status,
        )
        return row_id

    def get_next_pending_product(self) -> Optional[Product]:
        """
        Fetch the oldest product with status ``Pending``.

        Uses ``ORDER BY id ASC LIMIT 1`` to ensure FIFO processing.

        Returns:
            A ``Product`` instance, or ``None`` if no pending products exist.
        """
        sql = """
            SELECT * FROM products
             WHERE status = ?
             ORDER BY id ASC
             LIMIT 1
        """
        row = self._db.fetchone(sql, (Status.PENDING.value,))

        if row is None:
            logger.debug("No pending products found.")
            return None

        product = Product.from_row(row)
        logger.info(
            "Next pending product  │  id=%d  name=%s",
            product.id,
            product.product_name,
        )
        return product

    def update_status(self, product_id: int, status: str) -> None:
        """
        Update the status of a product.

        Args:
            product_id: The product's primary key.
            status:     New status value (use ``Status`` enum values).

        Raises:
            DatabaseQueryError: If the update fails.
        """
        sql = "UPDATE products SET status = ? WHERE id = ?"
        self._db.execute(sql, (status, product_id))
        logger.info(
            "Product status updated  │  id=%d  status=%s",
            product_id,
            status,
        )

    def update_image_path(self, product_id: int, image_path: str) -> None:
        """
        Set the image path for a product.

        Args:
            product_id: The product's primary key.
            image_path: Absolute or relative path to the image file.

        Raises:
            DatabaseQueryError: If the update fails.
        """
        sql = "UPDATE products SET image_path = ? WHERE id = ?"
        self._db.execute(sql, (image_path, product_id))
        logger.info(
            "Product image_path updated  │  id=%d  path=%s",
            product_id,
            image_path,
        )

    def update_title(self, product_id: int, title: str) -> None:
        """
        Set the generated title for a product.

        Args:
            product_id: The product's primary key.
            title:      The pin title text.

        Raises:
            DatabaseQueryError: If the update fails.
        """
        sql = "UPDATE products SET title = ? WHERE id = ?"
        self._db.execute(sql, (title, product_id))
        logger.info(
            "Product title updated  │  id=%d  title=%s",
            product_id,
            title[:50] if title else "",
        )

    def update_description(self, product_id: int, description: str) -> None:
        """
        Set the generated description for a product.

        Args:
            product_id:  The product's primary key.
            description: The pin description text.

        Raises:
            DatabaseQueryError: If the update fails.
        """
        sql = "UPDATE products SET description = ? WHERE id = ?"
        self._db.execute(sql, (description, product_id))
        logger.info(
            "Product description updated  │  id=%d  length=%d",
            product_id,
            len(description) if description else 0,
        )

    def update_affiliate_link(
        self, product_id: int, affiliate_link: str
    ) -> None:
        """
        Set the affiliate link for a product.

        Args:
            product_id:     The product's primary key.
            affiliate_link: The affiliate/referral URL.

        Raises:
            DatabaseQueryError: If the update fails.
        """
        sql = "UPDATE products SET affiliate_link = ? WHERE id = ?"
        self._db.execute(sql, (affiliate_link, product_id))
        logger.info(
            "Product affiliate_link updated  │  id=%d  link=%s",
            product_id,
            affiliate_link[:60] if affiliate_link else "",
        )

    def increase_retry(self, product_id: int) -> None:
        """
        Increment the retry counter for a product by 1.

        Typically called after a failed processing attempt before
        re-queuing the product.

        Args:
            product_id: The product's primary key.

        Raises:
            DatabaseQueryError: If the update fails.
        """
        sql = "UPDATE products SET retry_count = retry_count + 1 WHERE id = ?"
        self._db.execute(sql, (product_id,))
        logger.info("Product retry_count incremented  │  id=%d", product_id)

    # ═══════════════════════════════════════════════════════════════════
    #  LOGS
    # ═══════════════════════════════════════════════════════════════════

    def save_log(
        self,
        level: str,
        message: str,
        module: str = "",
    ) -> None:
        """
        Persist a log entry to the ``logs`` table.

        This complements Python's file-based logging by providing
        a queryable, structured log store in the database.

        Args:
            level:   Log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            message: Log message text.
            module:  Source module name.

        Raises:
            DatabaseQueryError: If the insert fails.
        """
        sql = """
            INSERT INTO logs (level, message, module)
            VALUES (?, ?, ?)
        """
        self._db.execute(sql, (level.upper(), message, module))
        logger.debug(
            "Log persisted  │  level=%s  module=%s  msg=%s",
            level,
            module,
            message[:80],
        )

    def get_logs(
        self,
        limit: int = 100,
        level: Optional[str] = None,
    ) -> list[LogEntry]:
        """
        Retrieve log entries from the ``logs`` table.

        Args:
            limit: Maximum number of rows to return (default 100).
            level: Optional filter by log level (e.g. ``"ERROR"``).

        Returns:
            A list of ``LogEntry`` instances ordered newest-first.
        """
        if level:
            sql = """
                SELECT * FROM logs
                 WHERE level = ?
                 ORDER BY id DESC
                 LIMIT ?
            """
            rows = self._db.fetchall(sql, (level.upper(), limit))
        else:
            sql = """
                SELECT * FROM logs
                 ORDER BY id DESC
                 LIMIT ?
            """
            rows = self._db.fetchall(sql, (limit,))

        entries = [LogEntry.from_row(row) for row in rows]
        logger.debug("Retrieved %d log entries (level=%s).", len(entries), level)
        return entries

    # ═══════════════════════════════════════════════════════════════════
    #  SETTINGS
    # ═══════════════════════════════════════════════════════════════════

    def save_setting(self, key: str, value: str) -> None:
        """
        Insert or update a setting (upsert).

        Uses SQLite's ``INSERT OR REPLACE`` to atomically create or
        overwrite the setting in a single statement.

        Args:
            key:   The setting identifier (primary key).
            value: The setting value.

        Raises:
            DatabaseQueryError: If the upsert fails.
        """
        sql = "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)"
        self._db.execute(sql, (key, value))
        logger.info("Setting saved  │  key=%s  value=%s", key, value[:50])

    def get_setting(self, key: str) -> Optional[str]:
        """
        Retrieve a setting value by key.

        Args:
            key: The setting identifier to look up.

        Returns:
            The setting value as a string, or ``None`` if not found.
        """
        sql = "SELECT value FROM settings WHERE key = ?"
        row = self._db.fetchone(sql, (key,))

        if row is None:
            logger.debug("Setting not found  │  key=%s", key)
            return None

        value = row["value"]
        logger.debug("Setting retrieved  │  key=%s  value=%s", key, value[:50])
        return value
