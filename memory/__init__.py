"""
Memory Module — Semantic vector storage and LLM context management.
=====================================================================

Provides comprehensive memory capabilities for the AI Agent:
    • ConversationMemory — Token-optimized chat history
    • ShortTermMemory    — Task execution tracking
    • LongTermMemory     — Semantic storage of failures and decisions
    • VectorStore        — SQLite-backed vector database
    • EmbeddingManager   — Text to vector transformation

Quick Start::

    from database import Database
    from memory import MemoryManager

    db = Database("database/pinterest_ai_agent.db")
    db.connect()

    memory = MemoryManager(db)
    await memory.remember("failure", "Captcha block", error_msg="Timeout")
    context = await memory.recall("captcha issues")

Public API:
    - MemoryManager        — Unified facade
    - ConversationMemory   — LLM message history
    - ShortTermMemory      — Current task state
    - LongTermMemory       — Semantic experiential storage
    - VectorStore          — Local vector database
    - EmbeddingManager     — Text embedding pipeline
"""

from memory.memory_manager import MemoryManager
from memory.conversation_memory import ConversationMemory, ChatMessage
from memory.short_term_memory import ShortTermMemory, ExecutionStep
from memory.long_term_memory import LongTermMemory
from memory.vector_store import VectorStore, SearchResult
from memory.embedding_manager import EmbeddingManager

__all__ = [
    "MemoryManager",
    "ConversationMemory",
    "ChatMessage",
    "ShortTermMemory",
    "ExecutionStep",
    "LongTermMemory",
    "VectorStore",
    "SearchResult",
    "EmbeddingManager",
]
