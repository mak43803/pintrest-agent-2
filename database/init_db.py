"""
Init DB — Schema creation and database bootstrapping.
======================================================

Responsible for creating all tables, indexes, and default data
when the application starts for the first time. Uses ``IF NOT EXISTS``
guards so it is safe to run on every startup — idempotent by design.

Tables created:
    1. ``products``  — Pinterest product items to be pinned
    2. ``tasks``     — Tracked agent tasks
    3. ``logs``      — Persisted log records
    4. ``settings``  — Key-value configuration store

Indexes:
    - ``idx_products_status``   — Fast lookup of pending products
    - ``idx_products_category`` — Filter products by category
    - ``idx_tasks_status``      — Fast lookup of active tasks
    - ``idx_logs_level``        — Filter logs by severity
    - ``idx_logs_created_at``   — Chronological log queries
"""

from __future__ import annotations

import logging

from database.database import Database

logger = logging.getLogger("pinterest_agent.database.init")


# ═══════════════════════════════════════════════════════════════════════
# SQL Schema Definitions
# ═══════════════════════════════════════════════════════════════════════

SQL_CREATE_PRODUCTS = """
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name    TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT '',
    board_name      TEXT    NOT NULL DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'Pending',
    image_path      TEXT,
    source_url      TEXT,
    title           TEXT,
    description     TEXT,
    affiliate_link  TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    pin_url         TEXT,
    impressions     INTEGER NOT NULL DEFAULT 0,
    clicks          INTEGER NOT NULL DEFAULT 0,
    saves           INTEGER NOT NULL DEFAULT 0,
    stats_updated_at TEXT
);
"""

SQL_CREATE_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name       TEXT    NOT NULL,
    current_step    TEXT    NOT NULL DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'Pending',
    started_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    finished_at     TEXT,
    last_error      TEXT
);
"""

SQL_CREATE_LOGS = """
CREATE TABLE IF NOT EXISTS logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    level           TEXT    NOT NULL,
    message         TEXT    NOT NULL,
    module          TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""

SQL_CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL DEFAULT ''
);
"""

SQL_CREATE_HEALED_SELECTORS = """
CREATE TABLE IF NOT EXISTS healed_selectors (
    original_selector TEXT PRIMARY KEY,
    healed_selector   TEXT NOT NULL,
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""

# ── Indexes ────────────────────────────────────────────────────────────

SQL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_products_status   ON products (status);",
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status      ON tasks    (status);",
    "CREATE INDEX IF NOT EXISTS idx_logs_level        ON logs     (level);",
    "CREATE INDEX IF NOT EXISTS idx_logs_created_at   ON logs     (created_at);",
]

# ── Trigger: auto-update ``updated_at`` on product modification ───────

SQL_TRIGGER_UPDATED_AT = """
CREATE TRIGGER IF NOT EXISTS trg_products_updated_at
AFTER UPDATE ON products
FOR EACH ROW
BEGIN
    UPDATE products
       SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
     WHERE id = OLD.id;
END;
"""


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def create_database(db: Database) -> None:
    """
    Initialize the database schema.

    Creates all tables, indexes, and triggers if they do not already
    exist. Safe to call on every application startup.

    Args:
        db: An initialized ``Database`` instance.

    Raises:
        DatabaseQueryError: If any DDL statement fails.
    """
    logger.info("Initializing database schema...")

    with db.connection() as conn:
        # ── Tables ─────────────────────────────────────────────────────
        conn.execute(SQL_CREATE_PRODUCTS)
        logger.debug("Table 'products' ready.")

        # Check and migrate columns if they don't exist
        cursor = conn.execute("PRAGMA table_info(products)")
        existing_columns = [row["name"] for row in cursor.fetchall()]
        
        migrations = [
            ("pin_url", "ALTER TABLE products ADD COLUMN pin_url TEXT;"),
            ("impressions", "ALTER TABLE products ADD COLUMN impressions INTEGER NOT NULL DEFAULT 0;"),
            ("clicks", "ALTER TABLE products ADD COLUMN clicks INTEGER NOT NULL DEFAULT 0;"),
            ("saves", "ALTER TABLE products ADD COLUMN saves INTEGER NOT NULL DEFAULT 0;"),
            ("stats_updated_at", "ALTER TABLE products ADD COLUMN stats_updated_at TEXT;"),
            ("audit_status", "ALTER TABLE products ADD COLUMN audit_status TEXT DEFAULT 'Pending';"),
            ("audit_last_checked", "ALTER TABLE products ADD COLUMN audit_last_checked TEXT;")
        ]
        
        for col_name, migration_sql in migrations:
            if col_name not in existing_columns:
                try:
                    conn.execute(migration_sql)
                    logger.info(f"Database Migration: Added column '{col_name}' to 'products' table.")
                except Exception as e:
                    logger.error(f"Failed to add column '{col_name}': {e}")

        conn.execute(SQL_CREATE_TASKS)
        logger.debug("Table 'tasks' ready.")

        conn.execute(SQL_CREATE_LOGS)
        logger.debug("Table 'logs' ready.")

        conn.execute(SQL_CREATE_SETTINGS)
        logger.debug("Table 'settings' ready.")

        conn.execute(SQL_CREATE_HEALED_SELECTORS)
        logger.debug("Table 'healed_selectors' ready.")

        # ── Indexes ────────────────────────────────────────────────────
        for index_sql in SQL_INDEXES:
            conn.execute(index_sql)
        logger.debug("All indexes created.")

        # ── Triggers ───────────────────────────────────────────────────
        conn.execute(SQL_TRIGGER_UPDATED_AT)
        logger.debug("Trigger 'trg_products_updated_at' ready.")

    logger.info(
        "Database schema initialized successfully  │  "
        "tables=[products, tasks, logs, settings]  │  "
        "path=%s",
        db.db_path.name,
    )
