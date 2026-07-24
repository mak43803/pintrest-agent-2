"""
Database — SQLite connection manager with thread-safe pooling.
===============================================================

Provides a production-grade connection manager for SQLite that:

    • Auto-creates the database file and parent directories
    • Enables WAL journal mode for concurrent read performance
    • Uses ``sqlite3.Row`` for dict-like column access
    • Enforces foreign keys
    • Manages a thread-local connection cache (one per thread)
    • Exposes a context-manager ``connection()`` for transaction safety
    • Logs all connection lifecycle events

Usage::

    db = Database("path/to/db.sqlite")
    db.connect()

    with db.connection() as conn:
        cursor = conn.execute("SELECT * FROM products")
        rows = cursor.fetchall()

    db.close()

Design Decisions:
    - Thread-local storage instead of a traditional pool because SQLite
      serializes writes at the filesystem level; one connection per thread
      avoids lock contention while remaining safe for multi-threaded apps.
    - ``autocommit = False`` by default; callers use ``connection()`` which
      commits on success and rolls back on exception.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from utils.exceptions import DatabaseConnectionError, DatabaseQueryError

logger = logging.getLogger("pinterest_agent.database")


class Database:
    """
    Thread-safe SQLite connection manager.

    Attributes:
        db_path:         Absolute path to the SQLite database file.
        journal_mode:    SQLite journal mode (default ``WAL``).
        busy_timeout_ms: Milliseconds to wait when the DB is locked.
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(
        self,
        db_path: str,
        journal_mode: str = "WAL",
        busy_timeout_ms: int = 5000,
    ) -> None:
        """
        Initialize the database manager.

        Args:
            db_path:         Path to the SQLite database file.
            journal_mode:    Journal mode (WAL recommended for reads).
            busy_timeout_ms: Lock wait timeout in milliseconds.
        """
        self._db_path = Path(db_path).resolve()
        self._journal_mode = journal_mode
        self._busy_timeout_ms = busy_timeout_ms
        self._local = threading.local()
        self._lock = threading.Lock()
        self._is_connected = False

        logger.debug(
            "Database manager created  │  path=%s  journal=%s  timeout=%dms",
            self._db_path,
            self._journal_mode,
            self._busy_timeout_ms,
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def db_path(self) -> Path:
        """Return the resolved database file path."""
        return self._db_path

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the current thread holds a connection."""
        return getattr(self._local, "connection", None) is not None

    # ── Connect / Close ────────────────────────────────────────────────

    def connect(self) -> sqlite3.Connection:
        """
        Open (or return the existing) connection for the current thread.

        The database file and its parent directories are created
        automatically if they do not exist.

        Returns:
            An open ``sqlite3.Connection`` configured with Row factory.

        Raises:
            DatabaseConnectionError: If the connection cannot be opened.
        """
        # Return cached connection if already open on this thread
        existing: sqlite3.Connection | None = getattr(
            self._local, "connection", None
        )
        if existing is not None:
            return existing

        try:
            # Ensure parent directory exists
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(
                str(self._db_path),
                timeout=self._busy_timeout_ms / 1000.0,
                check_same_thread=False,
            )

            # ── Configure connection pragmas ───────────────────────────
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute(f"PRAGMA journal_mode = {self._journal_mode};")
            conn.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms};")

            self._local.connection = conn
            self._is_connected = True

            logger.info(
                "Database connected  │  path=%s  thread=%s",
                self._db_path.name,
                threading.current_thread().name,
            )
            return conn

        except sqlite3.Error as exc:
            logger.error("Failed to connect to database: %s", exc)
            raise DatabaseConnectionError(
                f"Cannot open database at {self._db_path}: {exc}"
            ) from exc

    def close(self) -> None:
        """
        Close the connection for the current thread.

        Safe to call multiple times; does nothing if already closed.
        """
        conn: sqlite3.Connection | None = getattr(
            self._local, "connection", None
        )
        if conn is not None:
            try:
                conn.close()
                logger.info(
                    "Database connection closed  │  thread=%s",
                    threading.current_thread().name,
                )
            except sqlite3.Error as exc:
                logger.warning("Error closing database connection: %s", exc)
            finally:
                self._local.connection = None
                self._is_connected = False

    # ── Transaction Context Manager ────────────────────────────────────

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager that provides a connection with automatic
        commit/rollback semantics.

        On successful exit the transaction is committed.
        On exception the transaction is rolled back and the error
        is re-raised.

        Yields:
            An open ``sqlite3.Connection``.

        Raises:
            DatabaseConnectionError: If the connection cannot be opened.
            DatabaseQueryError: If a query within the block fails.

        Example::

            with db.connection() as conn:
                conn.execute("INSERT INTO ...", (...))
        """
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            logger.error("Transaction rolled back: %s", exc)
            raise DatabaseQueryError(
                f"Database query failed: {exc}"
            ) from exc
        except Exception:
            conn.rollback()
            raise

    # ── Convenience Executors ──────────────────────────────────────────

    def execute(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> sqlite3.Cursor:
        """
        Execute a single SQL statement with automatic commit.

        Args:
            sql:    SQL statement (use ``?`` placeholders).
            params: Bind parameters (tuple or dict).

        Returns:
            The resulting ``sqlite3.Cursor``.

        Raises:
            DatabaseQueryError: On any SQL error.
        """
        with self.connection() as conn:
            try:
                cursor = conn.execute(sql, params or ())
                return cursor
            except sqlite3.Error as exc:
                logger.error("Execute failed  │  sql=%s  error=%s", sql[:80], exc)
                raise DatabaseQueryError(f"Execute failed: {exc}") from exc

    def executemany(
        self,
        sql: str,
        params_seq: list[tuple] | list[dict],
    ) -> sqlite3.Cursor:
        """
        Execute a SQL statement against all parameter sequences.

        Args:
            sql:        SQL statement template.
            params_seq: Sequence of parameter tuples or dicts.

        Returns:
            The resulting ``sqlite3.Cursor``.

        Raises:
            DatabaseQueryError: On any SQL error.
        """
        with self.connection() as conn:
            try:
                cursor = conn.executemany(sql, params_seq)
                return cursor
            except sqlite3.Error as exc:
                logger.error("Executemany failed  │  sql=%s  error=%s", sql[:80], exc)
                raise DatabaseQueryError(f"Executemany failed: {exc}") from exc

    def fetchone(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> sqlite3.Row | None:
        """
        Execute a query and return the first row, or ``None``.

        Args:
            sql:    SELECT statement.
            params: Bind parameters.

        Returns:
            A ``sqlite3.Row`` or ``None`` if no results.
        """
        with self.connection() as conn:
            cursor = conn.execute(sql, params or ())
            return cursor.fetchone()

    def fetchall(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> list[sqlite3.Row]:
        """
        Execute a query and return all rows.

        Args:
            sql:    SELECT statement.
            params: Bind parameters.

        Returns:
            A list of ``sqlite3.Row`` objects (may be empty).
        """
        with self.connection() as conn:
            cursor = conn.execute(sql, params or ())
            return cursor.fetchall()

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Database(path={self._db_path.name!r}, "
            f"journal={self._journal_mode!r}, "
            f"connected={self.is_connected})"
        )
