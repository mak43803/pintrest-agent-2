"""
Log Manager — SQLite logging integration and analysis.
======================================================

Connects to the SQLite ``logs`` table (created in init_db.py).
Provides methods to search, filter, and export log records, making
it easy to diagnose agent behavior historically.

Features:
    • Store log records in SQLite
    • Filter logs by Level, Module, or Date range
    • Search logs via substring match
    • Export logs to JSON or CSV

Usage::

    from logs.log_manager import LogManager
    from database.database import Database
    
    db = Database(...)
    manager = LogManager(db)
    
    manager.save_log("ERROR", "Connection refused", "llm.client")
    errors = manager.filter_logs(level="ERROR")
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from database.database import Database

# We use the root python logger for internal LogManager messages
logger = logging.getLogger("pinterest_agent.logs.manager")


@dataclass
class LogRecord:
    """Represents a single log entry from the database."""
    id: int
    level: str
    message: str
    module: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class LogManager:
    """
    Manager for querying and exporting database-persisted logs.
    
    Args:
        db: An initialized SQLite Database instance.
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        logger.info("LogManager initialized.")

    # ── Writing ────────────────────────────────────────────────────────

    def save_log(self, level: str, message: str, module: str = "") -> int:
        """
        Save a log entry to SQLite.
        
        Args:
            level:   Log severity (e.g., INFO, ERROR, CRITICAL).
            message: The log message.
            module:  The component generating the log.
            
        Returns:
            The inserted row ID.
        """
        sql = "INSERT INTO logs (level, message, module) VALUES (?, ?, ?)"
        cursor = self._db.execute(sql, (level, message, module))
        return cursor.lastrowid

    # ── Querying ───────────────────────────────────────────────────────

    def filter_logs(
        self,
        level: str | None = None,
        module: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LogRecord]:
        """
        Filter logs by severity level or module.
        
        Args:
            level:  Exact match for log level (e.g., "ERROR").
            module: Exact match for module name.
            limit:  Max rows to return.
            offset: Pagination offset.
            
        Returns:
            List of LogRecord objects.
        """
        query = "SELECT * FROM logs"
        conditions = []
        params: list[Any] = []

        if level:
            conditions.append("level = ?")
            params.append(level.upper())
        if module:
            conditions.append("module = ?")
            params.append(module)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._db.fetchall(query, tuple(params))
        return [LogRecord(**row) for row in rows]

    def search_logs(self, keyword: str, limit: int = 100) -> list[LogRecord]:
        """
        Search for a specific keyword in the log messages.
        
        Args:
            keyword: The substring to search for.
            limit:   Max rows to return.
            
        Returns:
            List of matching LogRecord objects.
        """
        query = "SELECT * FROM logs WHERE message LIKE ? ORDER BY id DESC LIMIT ?"
        # SQLite LIKE uses % for wildcards
        search_term = f"%{keyword}%"
        
        rows = self._db.fetchall(query, (search_term, limit))
        return [LogRecord(**row) for row in rows]

    def get_recent_logs(self, limit: int = 50) -> list[LogRecord]:
        """Fetch the most recent log entries."""
        return self.filter_logs(limit=limit)

    # ── Exporting ──────────────────────────────────────────────────────

    def export_to_json(self, filepath: str | Path, limit: int = 1000) -> None:
        """
        Export recent logs to a JSON file.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        logs = self.get_recent_logs(limit=limit)
        data = [log.to_dict() for log in logs]
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        logger.info("Logs exported to JSON  │  file=%s  count=%d", path.name, len(logs))

    def export_to_csv(self, filepath: str | Path, limit: int = 1000) -> None:
        """
        Export recent logs to a CSV file.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        logs = self.get_recent_logs(limit=limit)
        if not logs:
            logger.warning("No logs to export.")
            return
            
        with open(path, "w", encoding="utf-8", newline="") as f:
            # We use the keys of the first record as CSV headers
            fieldnames = list(logs[0].to_dict().keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            for log in logs:
                writer.writerow(log.to_dict())
                
        logger.info("Logs exported to CSV  │  file=%s  count=%d", path.name, len(logs))
