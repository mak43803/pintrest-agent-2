"""
Memory — Conversation memory and session management.
=====================================================

Manages the ordered list of conversation messages (system, user,
assistant) that form the context window for LLM calls. Supports:

    • System prompt injection (always first message)
    • Message history with configurable max length
    • Session save/load to JSON files for persistence
    • Memory trimming to fit within token budgets
    • Full history export for debugging

Design:
    - Messages are stored as a simple list of dicts with ``role``
      and ``content`` keys — the native format expected by the
      Ollama ``/api/chat`` endpoint.
    - The system prompt is always index 0 and is never trimmed.
    - When ``max_messages`` is exceeded, the oldest non-system
      messages are removed (FIFO eviction).

Usage::

    from llm.memory import ConversationMemory

    memory = ConversationMemory(system_prompt="You are a helpful agent.")
    memory.add_user_message("Search for earbuds on Pinterest")
    memory.add_assistant_message("I'll search for earbuds now...")

    messages = memory.get_messages()  # ready for Ollama API
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("pinterest_agent.llm.memory")


class ConversationMemory:
    """
    Conversation memory with system prompt support and persistence.

    Maintains a bounded list of messages in the Ollama chat format:
    ``[{"role": "system"|"user"|"assistant", "content": "..."}]``

    Args:
        system_prompt: The system prompt injected at position 0.
        max_messages:  Maximum number of messages to retain
                       (excluding the system prompt). Oldest
                       messages are evicted when this limit is exceeded.
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(
        self,
        system_prompt: str = "",
        max_messages: int = 50,
    ) -> None:
        self._system_prompt = system_prompt
        self._max_messages = max_messages
        self._messages: list[dict[str, str]] = []
        self._session_id: str = self._generate_session_id()

        # Initialize with system prompt if provided
        if system_prompt:
            self._messages.append({
                "role": "system",
                "content": system_prompt,
            })

        logger.info(
            "ConversationMemory created  │  session=%s  max_messages=%d  "
            "has_system_prompt=%s",
            self._session_id,
            self._max_messages,
            bool(system_prompt),
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def session_id(self) -> str:
        """Return the current session identifier."""
        return self._session_id

    @property
    def system_prompt(self) -> str:
        """Return the system prompt."""
        return self._system_prompt

    @property
    def message_count(self) -> int:
        """Return the number of non-system messages."""
        system_count = 1 if self._system_prompt else 0
        return len(self._messages) - system_count

    @property
    def total_count(self) -> int:
        """Return the total number of messages including system prompt."""
        return len(self._messages)

    # ── Add Messages ───────────────────────────────────────────────────

    def add_user_message(self, content: str) -> None:
        """
        Append a user message to the conversation.

        Args:
            content: The user's message text.
        """
        self._messages.append({"role": "user", "content": content})
        self._trim()
        logger.debug(
            "User message added  │  length=%d  total=%d",
            len(content),
            self.total_count,
        )

    def add_assistant_message(self, content: str) -> None:
        """
        Append an assistant message to the conversation.

        Args:
            content: The assistant's response text.
        """
        self._messages.append({"role": "assistant", "content": content})
        self._trim()
        logger.debug(
            "Assistant message added  │  length=%d  total=%d",
            len(content),
            self.total_count,
        )

    def add_message(self, role: str, content: str) -> None:
        """
        Append a message with an arbitrary role.

        Args:
            role:    Message role (``system``, ``user``, ``assistant``).
            content: The message text.
        """
        self._messages.append({"role": role, "content": content})
        self._trim()

    # ── Read Messages ──────────────────────────────────────────────────

    def get_messages(self) -> list[dict[str, str]]:
        """
        Return the full message list ready for the Ollama API.

        Returns:
            A shallow copy of the messages list.
        """
        return list(self._messages)

    def get_last_message(self) -> dict[str, str] | None:
        """
        Return the most recent message, or ``None`` if empty.

        Returns:
            The last message dict, or ``None``.
        """
        return self._messages[-1] if self._messages else None

    def get_last_assistant_message(self) -> str | None:
        """
        Return the content of the most recent assistant message.

        Returns:
            The assistant's last response text, or ``None``.
        """
        for msg in reversed(self._messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return None

    # ── System Prompt ──────────────────────────────────────────────────

    def set_system_prompt(self, prompt: str) -> None:
        """
        Set or replace the system prompt.

        If a system prompt already exists at index 0, it is replaced.
        Otherwise a new system message is inserted at position 0.

        Args:
            prompt: The new system prompt text.
        """
        self._system_prompt = prompt

        if self._messages and self._messages[0]["role"] == "system":
            self._messages[0]["content"] = prompt
        else:
            self._messages.insert(0, {"role": "system", "content": prompt})

        logger.info("System prompt updated  │  length=%d", len(prompt))

    # ── Clear ──────────────────────────────────────────────────────────

    def clear(self) -> None:
        """
        Clear all messages except the system prompt.

        After clearing, only the system prompt (if any) remains.
        """
        self._messages.clear()

        if self._system_prompt:
            self._messages.append({
                "role": "system",
                "content": self._system_prompt,
            })

        self._session_id = self._generate_session_id()
        logger.info("Conversation memory cleared  │  new_session=%s", self._session_id)

    # ── Persistence ────────────────────────────────────────────────────

    def save_to_file(self, filepath: str | Path) -> None:
        """
        Save the conversation history to a JSON file.

        Args:
            filepath: Path to the output JSON file.

        Raises:
            OSError: If the file cannot be written.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "session_id": self._session_id,
            "system_prompt": self._system_prompt,
            "max_messages": self._max_messages,
            "messages": self._messages,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(
            "Conversation saved  │  path=%s  messages=%d",
            path.name,
            len(self._messages),
        )

    @classmethod
    def load_from_file(cls, filepath: str | Path) -> ConversationMemory:
        """
        Load a conversation from a JSON file.

        Args:
            filepath: Path to the JSON file to load.

        Returns:
            A new ``ConversationMemory`` instance with the loaded state.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        path = Path(filepath)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        instance = cls(
            system_prompt=data.get("system_prompt", ""),
            max_messages=data.get("max_messages", 50),
        )

        # Replace messages with loaded data (skip re-adding system prompt)
        instance._messages = data.get("messages", [])
        instance._session_id = data.get("session_id", instance._session_id)

        logger.info(
            "Conversation loaded  │  path=%s  session=%s  messages=%d",
            path.name,
            instance._session_id,
            len(instance._messages),
        )
        return instance

    # ── Export ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full memory state to a dictionary."""
        return {
            "session_id": self._session_id,
            "system_prompt": self._system_prompt,
            "max_messages": self._max_messages,
            "message_count": self.message_count,
            "messages": list(self._messages),
        }

    # ── Internal ───────────────────────────────────────────────────────

    def _trim(self) -> None:
        """
        Evict the oldest non-system messages if the limit is exceeded.

        The system prompt (index 0) is always preserved.
        """
        system_offset = 1 if (self._messages and self._messages[0]["role"] == "system") else 0
        non_system_count = len(self._messages) - system_offset

        while non_system_count > self._max_messages:
            removed = self._messages.pop(system_offset)
            non_system_count -= 1
            logger.debug(
                "Message evicted (memory full)  │  role=%s  length=%d",
                removed["role"],
                len(removed["content"]),
            )

    @staticmethod
    def _generate_session_id() -> str:
        """Generate a timestamp-based session identifier."""
        return datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"ConversationMemory(session={self._session_id!r}, "
            f"messages={self.total_count}, "
            f"max={self._max_messages})"
        )

    def __len__(self) -> int:
        return self.total_count
