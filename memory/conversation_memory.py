"""
Conversation Memory — Manages LLM chat history and summarization.
==================================================================

Responsible for storing the immediate back-and-forth dialogue with
the LLM. Provides token optimization and automatic summarization
to prevent the context window from growing indefinitely.

Features:
    • Bounded message list (FIFO eviction)
    • Token estimation (naive heuristic for speed)
    • Automatic summarization of older messages
    • JSON persistence

Usage::

    from memory.conversation_memory import ConversationMemory

    mem = ConversationMemory(max_tokens=4000)
    mem.add_message("user", "Hello")
    mem.add_message("assistant", "Hi there")
    
    messages = mem.get_context()
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("pinterest_agent.memory.conversation")


@dataclass
class ChatMessage:
    """A single message in the conversation history."""
    role: str
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    tokens: int = field(init=False)

    def __post_init__(self) -> None:
        # Naive token estimation: ~4 chars per token
        self.tokens = len(self.content) // 4 + 1

    def to_dict(self) -> dict[str, str]:
        """Convert to the standard format expected by the LLM."""
        return {"role": self.role, "content": self.content}


class ConversationMemory:
    """
    Manages short-term conversation context for the LLM.

    Args:
        max_messages: Maximum raw messages to keep before summarizing/evicting.
        max_tokens:   Maximum token count allowed in the context window.
    """

    def __init__(self, max_messages: int = 50, max_tokens: int = 4096) -> None:
        self._max_messages = max_messages
        self._max_tokens = max_tokens
        self._messages: list[ChatMessage] = []
        self._system_prompt: str = ""
        self._summary: str = ""
        logger.info(
            "ConversationMemory initialized  │  max_msg=%d  max_tokens=%d",
            max_messages,
            max_tokens,
        )

    # ── Core API ───────────────────────────────────────────────────────

    def set_system_prompt(self, prompt: str) -> None:
        """Set the base system prompt for the agent."""
        self._system_prompt = prompt

    def add_message(self, role: str, content: str) -> None:
        """Add a new message and auto-optimize if limits are exceeded."""
        msg = ChatMessage(role=role, content=content)
        self._messages.append(msg)
        self._optimize_context()
        logger.debug("Added message  │  role=%s  tokens=%d", role, msg.tokens)

    def get_context(self) -> list[dict[str, str]]:
        """
        Build the full prompt context for the LLM.

        Structure:
            1. System Prompt
            2. Summary of past conversation (if any)
            3. Recent messages
        """
        context: list[dict[str, str]] = []

        if self._system_prompt:
            context.append({"role": "system", "content": self._system_prompt})

        if self._summary:
            context.append({
                "role": "system",
                "content": f"Summary of earlier conversation: {self._summary}"
            })

        for msg in self._messages:
            context.append(msg.to_dict())

        return context

    def clear(self) -> None:
        """Clear all conversation history and summaries."""
        self._messages.clear()
        self._summary = ""
        logger.info("Conversation memory cleared.")

    # ── Summarization & Optimization ───────────────────────────────────

    def _optimize_context(self) -> None:
        """
        Enforce token and message limits.

        If limits are exceeded, older messages are dropped.
        (A real implementation would call the LLM to summarize the dropped
        messages, but here we simulate it by truncating).
        """
        current_tokens = sum(m.tokens for m in self._messages)
        
        while len(self._messages) > self._max_messages or current_tokens > self._max_tokens:
            if not self._messages:
                break
                
            # Evict the oldest message
            evicted = self._messages.pop(0)
            current_tokens -= evicted.tokens
            
            # Simple summary update (placeholder for LLM summarization)
            if not self._summary:
                self._summary = "Previous context truncated due to length."
                
            logger.debug("Evicted message  │  role=%s  tokens=%d", evicted.role, evicted.tokens)

    def summarize(self, summary_text: str) -> None:
        """
        Explicitly inject a summary and clear older messages.
        
        Called by the LLMManager when it decides the context is too long.
        """
        self._summary = summary_text
        self._messages = self._messages[-5:]  # Keep only last 5 messages for continuity
        logger.info("Conversation summarized.")

    # ── Persistence ────────────────────────────────────────────────────

    def save(self, filepath: str | Path) -> None:
        """Save conversation state to disk."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "system_prompt": self._system_prompt,
            "summary": self._summary,
            "messages": [asdict(m) for m in self._messages],
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
    def load(self, filepath: str | Path) -> None:
        """Load conversation state from disk."""
        path = Path(filepath)
        if not path.exists():
            return
            
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self._system_prompt = data.get("system_prompt", "")
        self._summary = data.get("summary", "")
        
        self._messages.clear()
        for m in data.get("messages", []):
            self._messages.append(
                ChatMessage(
                    role=m["role"],
                    content=m["content"],
                    timestamp=m.get("timestamp", ""),
                )
            )
        logger.info("Conversation loaded  │  messages=%d", len(self._messages))
