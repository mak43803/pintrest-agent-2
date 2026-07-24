"""
Database Module — Production-grade SQLite persistence layer.
=============================================================

Provides a complete data-access layer using SQLite with the
Repository Pattern. Auto-creates the database and schema on
first run.

Quick Start::

    from database import Database, Repository, create_database

    db = Database("database/pinterest_ai_agent.db")
    db.connect()
    create_database(db)

    repo = Repository(db)
    product_id = repo.insert_product(product_name="Widget", category="Tech")

Public API:
    - Database          — Thread-safe connection manager
    - Repository        — Data access object (all CRUD operations)
    - create_database   — Idempotent schema bootstrapper
    - Product           — Product data model
    - Task              — Task data model
    - LogEntry          — Log entry data model
    - Setting           — Key-value setting model
    - Status            — Lifecycle status enum
"""

from database.database import Database
from database.models import LogEntry, Product, Setting, Status, Task
from database.repository import Repository
from database.init_db import create_database

__all__ = [
    "Database",
    "Repository",
    "create_database",
    "Product",
    "Task",
    "LogEntry",
    "Setting",
    "Status",
]
