"""
Memory Manager — Top-level orchestrator for the Memory System.
================================================================

Composes ConversationMemory, ShortTermMemory, and LongTermMemory
into a unified API. Provides the agent with a single interface to
manage all forms of context, history, and learnings.

Public API:
    - ``remember()``  → Stores a semantic memory in LTM
    - ``recall()``    → Fetches relevant memories from LTM
    - ``forget()``    → (Not implemented for immutable LTM, clears STM/Conv)
    - ``search()``    → Direct semantic search
    - ``summarize()`` → Triggers conversation summary
    - ``clear()``     → Wipes specific or all memory systems
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from database.database import Database
from memory.conversation_memory import ConversationMemory
from memory.embedding_manager import EmbeddingManager
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import ShortTermMemory
from memory.vector_store import VectorStore

logger = logging.getLogger("pinterest_agent.memory")


class MemoryManager:
    """
    Unified memory orchestrator for the Pinterest AI Agent.

    Args:
        db:           Initialized SQLite Database connection.
        max_conv_msg: Max raw messages in conversation memory.
        max_tokens:   Max token limit for conversation context.
    """

    def __init__(
        self,
        db: Database,
        max_conv_msg: int = 50,
        max_tokens: int = 4096,
    ) -> None:
        self._db = db

        # ── Initialize Subsystems ──────────────────────────────────────
        self._conversation = ConversationMemory(
            max_messages=max_conv_msg,
            max_tokens=max_tokens,
        )
        self._short_term = ShortTermMemory()

        self._vector_store = VectorStore(db)
        self._embedding_manager = EmbeddingManager()
        self._long_term = LongTermMemory(
            store=self._vector_store,
            embeddings=self._embedding_manager,
        )

        logger.info("MemoryManager initialized  │  All subsystems ready.")

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def conversation(self) -> ConversationMemory:
        """Access the Conversation Memory subsystem."""
        return self._conversation

    @property
    def short_term(self) -> ShortTermMemory:
        """Access the Short-Term Memory subsystem."""
        return self._short_term

    @property
    def long_term(self) -> LongTermMemory:
        """Access the Long-Term Memory subsystem."""
        return self._long_term

    # ── Unified Core API ───────────────────────────────────────────────

    async def remember(
        self,
        memory_type: str,
        content: str,
        **metadata: Any,
    ) -> int | None:
        """
        Store a permanent record in Long-Term Memory.

        Args:
            memory_type: "task", "failure", or "decision".
            content:     The core text to remember.
            **metadata:  Additional tags.

        Returns:
            The memory ID, or None if type is invalid.
        """
        if memory_type == "task":
            task_name = metadata.pop("task_name", "unknown_task")
            return await self._long_term.remember_task(task_name, content, **metadata)
            
        elif memory_type == "failure":
            error_msg = metadata.pop("error_msg", "Unknown error")
            return await self._long_term.remember_failure(content, error_msg, **metadata)
            
        elif memory_type == "decision":
            rationale = metadata.pop("rationale", "No rationale provided")
            return await self._long_term.remember_decision(content, rationale, **metadata)
            
        else:
            logger.error("Unknown memory_type '%s' for remember()", memory_type)
            return None

    async def recall(self, query: str, limit: int = 3) -> str:
        """
        Fetch relevant memories from Long-Term Memory as a formatted string.
        
        Useful for injecting past context directly into a system prompt.

        Args:
            query: The semantic search string.
            limit: Max results.

        Returns:
            A formatted string of relevant past memories, or empty string.
        """
        results = await self._long_term.recall(query, limit=limit)
        if not results:
            return ""
            
        formatted = "\\n".join(f"- {res}" for res in results)
        return f"Relevant past context:\\n{formatted}"

    async def search(self, query: str, limit: int = 5) -> list[str]:
        """
        Direct semantic search against Long-Term Memory.
        Returns the raw list of strings instead of a formatted block.
        """
        return await self._long_term.recall(query, limit=limit)

    def summarize(self, new_summary: str) -> None:
        """
        Force a summarization of the conversation history.
        """
        self._conversation.summarize(new_summary)

    def forget(self) -> None:
        """
        Alias for clearing short-term and conversation context.
        Does NOT wipe long-term semantic storage.
        """
        self._conversation.clear()
        self._short_term.clear()
        logger.info("MemoryManager: Forgotten current context (STM and Conv wiped).")

    def clear(self, all_systems: bool = False) -> None:
        """
        Wipe memory subsystems.
        
        Args:
            all_systems: If True, also wipes Long-Term Vector DB.
                         CAUTION: Destructive!
        """
        self.forget()
        if all_systems:
            self._long_term.clear()
            logger.warning("MemoryManager: ALL memory systems wiped, including LTM.")

    # ── Context Builder ────────────────────────────────────────────────

    async def build_agent_context(self, task_query: str) -> list[dict[str, str]]:
        """
        Assemble the full context for the LLM.
        
        Includes:
            1. Long-term memory retrieval based on current task
            2. Short-term task context variables
            3. Conversation history
            
        Returns:
            A list of messages ready for the LLM.
        """
        # 1. Fetch LTM
        ltm_context = await self.recall(task_query)
        
        # 2. Fetch STM
        stm_data = self._short_term.get_all_context()
        stm_context = ""
        if stm_data:
            stm_lines = [f"{k}: {v}" for k, v in stm_data.items()]
            stm_context = "Current Task Data:\\n" + "\\n".join(stm_lines)
            
        # 3. Combine into a dynamic system prompt override
        base_prompt = self._conversation.get_context()[0]["content"] if self._conversation.get_context() else ""
        
        combined_system = base_prompt
        if ltm_context or stm_context:
            combined_system += f"\\n\\n{ltm_context}\\n\\n{stm_context}"
            
        # We don't overwrite the base prompt, we just build a fresh message list
        # for this specific generation call.
        messages: list[dict[str, str]] = []
        messages.append({"role": "system", "content": combined_system.strip()})
        
        # Add conversation summary and history (skipping the original system prompt)
        messages.extend(self._conversation.get_context()[1:])
        
        return messages

    # ── Persistence ────────────────────────────────────────────────────

    def save_conversation(self, filepath: str | Path) -> None:
        """Save conversation memory to disk."""
        self._conversation.save(filepath)

    def load_conversation(self, filepath: str | Path) -> None:
        """Load conversation memory from disk."""
        self._conversation.load(filepath)
