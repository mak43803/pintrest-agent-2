"""
Vector Store — Persistent storage for embeddings and semantic search.
======================================================================

Currently backed by SQLite for zero-dependency local storage.
Designed to be drop-in replaceable with FAISS or ChromaDB in the future.

Features:
    • Stores text documents with associated vector embeddings
    • Stores metadata (JSON) alongside documents
    • Performs cosine similarity search (in-memory for SQLite)
    • Auto-initializes its own SQLite table (``memory_store``)

Usage::

    from memory.vector_store import VectorStore
    from database import Database

    store = VectorStore(db)
    store.insert("Avoid using hashtags in descriptions", vector=[0.1, ...])
    results = store.search(vector=[0.1, ...], limit=3)
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from database.database import Database

logger = logging.getLogger("pinterest_agent.memory.vector_store")


@dataclass
class SearchResult:
    """A single result from a vector search."""
    id: int
    content: str
    metadata: dict[str, Any]
    score: float  # 1.0 = perfect match, 0.0 = completely orthogonal


class VectorStore:
    """
    Storage engine for long-term semantic memory.

    Currently uses SQLite for persistence and performs naive in-memory
    cosine similarity for searches. Future-ready for FAISS/ChromaDB.

    Args:
        db: Initialized SQLite ``Database`` instance.
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        self._init_schema()
        logger.info("VectorStore initialized.")

    def _init_schema(self) -> None:
        """Create the memory_store table if it doesn't exist."""
        sql = """
            CREATE TABLE IF NOT EXISTS memory_store (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                content    TEXT NOT NULL,
                embedding  TEXT NOT NULL, -- JSON array of floats
                metadata   TEXT NOT NULL, -- JSON object
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
        """
        self._db.execute(sql)
        logger.debug("VectorStore schema verified.")

    def insert(
        self,
        content: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Insert a new memory with its embedding vector.

        Args:
            content:  The text content to remember.
            vector:   The embedding vector (list of floats).
            metadata: Optional key-value tags.

        Returns:
            The auto-generated ID of the stored memory.
        """
        meta = metadata or {}
        sql = """
            INSERT INTO memory_store (content, embedding, metadata)
            VALUES (?, ?, ?)
        """
        cursor = self._db.execute(
            sql,
            (content, json.dumps(vector), json.dumps(meta))
        )
        mem_id = cursor.lastrowid
        logger.debug("Memory inserted  │  id=%d", mem_id)
        return mem_id

    def search(self, vector: list[float], limit: int = 5) -> list[SearchResult]:
        """
        Search for the most semantically similar memories.

        Performs a brute-force cosine similarity search in Python.
        Fine for hundreds/thousands of records; FAISS recommended for more.

        Args:
            vector: The query embedding.
            limit:  Max results to return.

        Returns:
            List of ``SearchResult`` ordered by descending score.
        """
        sql = "SELECT id, content, embedding, metadata FROM memory_store"
        rows = self._db.fetchall(sql)

        results: list[SearchResult] = []
        for row in rows:
            try:
                db_vector: list[float] = json.loads(row["embedding"])
                score = self._cosine_similarity(vector, db_vector)
                
                results.append(
                    SearchResult(
                        id=row["id"],
                        content=row["content"],
                        metadata=json.loads(row["metadata"]),
                        score=score,
                    )
                )
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                logger.warning("Failed to parse vector for memory %d: %s", row["id"], exc)
                continue

        # Sort by score descending and truncate
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def update(
        self,
        memory_id: int,
        content: str | None = None,
        vector: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update an existing memory entry."""
        updates = []
        params = []
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if vector is not None:
            updates.append("embedding = ?")
            params.append(json.dumps(vector))
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
            
        if not updates:
            return
            
        sql = f"UPDATE memory_store SET {', '.join(updates)} WHERE id = ?"
        params.append(memory_id)
        self._db.execute(sql, tuple(params))
        logger.debug("Memory updated  │  id=%d", memory_id)

    def clear(self) -> None:
        """Wipe all memories from the store."""
        self._db.execute("DELETE FROM memory_store")
        logger.warning("VectorStore completely cleared.")

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
            
        return dot_product / (norm1 * norm2)
