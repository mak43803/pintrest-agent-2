"""
Long-Term Memory — Semantic storage for past experiences.
==========================================================

Uses the VectorStore and EmbeddingManager to persist abstract
learnings, past task results, and failure post-mortems so the
agent can learn and avoid repeating mistakes over time.

Features:
    • Remember completed tasks
    • Record failures and why they happened
    • Store important abstract decisions
    • Retrieve context based on semantic similarity

Usage::

    from memory.long_term_memory import LongTermMemory

    ltm = LongTermMemory(vector_store, embedding_manager)
    await ltm.remember_failure("Login block", "Pinterest showed captcha")
    
    similar = await ltm.recall("captcha issue")
"""

from __future__ import annotations

import logging
from typing import Any

from memory.embedding_manager import EmbeddingManager
from memory.vector_store import SearchResult, VectorStore

logger = logging.getLogger("pinterest_agent.memory.long_term")


class LongTermMemory:
    """
    Semantic long-term storage for agent experiences.

    Args:
        store:      Initialized VectorStore instance.
        embeddings: Initialized EmbeddingManager instance.
    """

    def __init__(self, store: VectorStore, embeddings: EmbeddingManager) -> None:
        self._store = store
        self._embeddings = embeddings
        logger.info("LongTermMemory initialized.")

    # ── Write Methods ──────────────────────────────────────────────────

    async def remember_task(
        self,
        task_name: str,
        summary: str,
        **metadata: Any,
    ) -> int:
        """
        Record a successfully completed task.

        Args:
            task_name: Human-readable name of the task.
            summary:   What was accomplished.
            **metadata: Additional context tags.
        """
        content = f"Task '{task_name}' completed: {summary}"
        meta = {"type": "task_completion", "task_name": task_name, **metadata}
        
        vector = await self._embeddings.get_embedding(content)
        mem_id = self._store.insert(content, vector, metadata=meta)
        
        logger.info("Remembered task completion  │  id=%d", mem_id)
        return mem_id

    async def remember_failure(
        self,
        context: str,
        error_msg: str,
        **metadata: Any,
    ) -> int:
        """
        Record a failure to avoid repeating it.

        Args:
            context:   What the agent was trying to do.
            error_msg: The error that occurred.
            **metadata: Additional context tags.
        """
        content = f"Failed while trying to '{context}'. Error: {error_msg}"
        meta = {"type": "failure", "context": context, **metadata}
        
        vector = await self._embeddings.get_embedding(content)
        mem_id = self._store.insert(content, vector, metadata=meta)
        
        logger.warning("Remembered failure  │  id=%d  error=%s", mem_id, error_msg[:50])
        return mem_id

    async def remember_decision(
        self,
        decision_context: str,
        rationale: str,
        **metadata: Any,
    ) -> int:
        """
        Record an abstract decision made by the planner/LLM.

        Args:
            decision_context: The situation or choice presented.
            rationale:        Why the decision was made.
            **metadata:       Additional context tags.
        """
        content = f"Decision made regarding '{decision_context}': {rationale}"
        meta = {"type": "decision", "context": decision_context, **metadata}
        
        vector = await self._embeddings.get_embedding(content)
        mem_id = self._store.insert(content, vector, metadata=meta)
        
        logger.info("Remembered decision  │  id=%d", mem_id)
        return mem_id

    # ── Read Methods ───────────────────────────────────────────────────

    async def recall(
        self,
        query: str,
        limit: int = 3,
        threshold: float = 0.5,
    ) -> list[str]:
        """
        Search for past memories semantically similar to the query.

        Args:
            query:     The search text.
            limit:     Max number of results to return.
            threshold: Minimum cosine similarity score (0.0 to 1.0).

        Returns:
            List of memory content strings that match.
        """
        vector = await self._embeddings.get_embedding(query)
        results = self._store.search(vector, limit=limit)
        
        valid = [r.content for r in results if r.score >= threshold]
        
        logger.debug(
            "Recalled memories  │  query='%s'  found=%d  valid=%d",
            query,
            len(results),
            len(valid),
        )
        return valid

    def clear(self) -> None:
        """Wipe all long-term memories from the vector store."""
        self._store.clear()
        logger.info("Long-term memory cleared.")
