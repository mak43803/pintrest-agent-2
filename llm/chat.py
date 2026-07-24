"""
Chat — High-level LLM Manager orchestrating client, memory, and prompts.
==========================================================================

The ``LLMManager`` is the single public entry point for all LLM
interactions in the application. It composes:

    • ``OllamaClient``       — low-level HTTP transport (llm.py)
    • ``ConversationMemory`` — message history & persistence (memory.py)
    • ``PromptManager``      — template formatting & system prompt (prompt_manager.py)

into a unified, production-ready interface with:

    • ``initialize()``    — connect to Ollama, verify model, set up memory
    • ``chat()``          — send a message and get a full response
    • ``stream_chat()``   — send a message and yield tokens in real-time
    • ``health_check()``  — verify Ollama connectivity
    • ``change_model()``  — hot-swap the active model
    • ``clear_memory()``  — reset conversation history
    • ``save_history()``  — persist conversation to disk
    • ``load_history()``  — restore conversation from disk

Usage::

    from llm.chat import LLMManager

    manager = LLMManager()
    await manager.initialize()

    # Full response
    response = await manager.chat("Search for earbuds on Pinterest")
    print(response)

    # Streaming
    async for token in manager.stream_chat("Find trending home decor"):
        print(token, end="", flush=True)

    await manager.shutdown()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncGenerator

from config.settings import get_settings, OllamaSettings
from llm.llm import GenerationConfig, LLMResponse, OllamaClient
from llm.memory import ConversationMemory
from llm.prompt_manager import PromptManager
from prompts.system_prompts import SYSTEM_PROMPT
from utils.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMResponseParseError,
    LLMTimeoutError,
)

logger = logging.getLogger("pinterest_agent.llm.chat")


class LLMManager:
    """
    High-level LLM orchestrator — the only class other modules
    need to import for all LLM interactions.

    Composes ``OllamaClient``, ``ConversationMemory``, and
    ``PromptManager`` behind a clean async API. Manages the full
    lifecycle: connection, generation, memory, and persistence.

    Args:
        settings:      Optional ``OllamaSettings`` override (uses
                       global settings if ``None``).
        system_prompt: Optional system prompt override (uses the
                       default from ``system_prompts.py`` if ``None``).
        max_memory:    Maximum conversation messages to retain.
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(
        self,
        settings: OllamaSettings | None = None,
        system_prompt: str | None = None,
        max_memory: int = 50,
    ) -> None:
        self._settings = settings or get_settings().ollama
        self._system_prompt = system_prompt or SYSTEM_PROMPT

        # ── Compose subsystems ─────────────────────────────────────────
        self._client = OllamaClient(
            base_url=self._settings.base_url,
            model=self._settings.model,
            timeout_seconds=self._settings.timeout_seconds,
            max_retries=self._settings.max_retries,
            retry_delay_seconds=self._settings.retry_delay_seconds,
        )

        self._memory = ConversationMemory(
            system_prompt=self._system_prompt,
            max_messages=max_memory,
        )

        self._prompt_manager = PromptManager(
            default_system_prompt=self._system_prompt,
        )

        self._default_config = GenerationConfig(
            temperature=self._settings.temperature,
            max_tokens=self._settings.max_tokens,
            top_p=self._settings.top_p,
        )

        self._is_initialized = False

        logger.info(
            "LLMManager created  │  model=%s  url=%s  max_memory=%d",
            self._settings.model,
            self._settings.base_url,
            max_memory,
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def is_initialized(self) -> bool:
        """Return whether the manager has been initialized."""
        return self._is_initialized

    @property
    def model(self) -> str:
        """Return the currently active model name."""
        return self._client.model

    @property
    def memory(self) -> ConversationMemory:
        """Return the conversation memory instance (read-only access)."""
        return self._memory

    @property
    def prompt_manager(self) -> PromptManager:
        """Return the prompt manager instance."""
        return self._prompt_manager

    @property
    def client(self) -> OllamaClient:
        """Return the underlying Ollama client (advanced usage)."""
        return self._client

    # ═══════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════

    async def initialize(self) -> None:
        """
        Initialize the LLM subsystem.

        Steps:
            1. Open the HTTP session to Ollama
            2. Verify Ollama server is running
            3. Verify the configured model is available
            4. Mark the manager as ready

        Raises:
            LLMConnectionError:    If Ollama is unreachable.
            LLMModelNotFoundError: If the model is not pulled.
        """
        logger.info("Initializing LLMManager...")

        await self._client.initialize()
        self._is_initialized = True

        logger.info(
            "LLMManager initialized  │  model=%s  session=%s",
            self._client.model,
            self._memory.session_id,
        )

    async def shutdown(self) -> None:
        """
        Shut down the LLM subsystem and release resources.

        Closes the HTTP session. Safe to call multiple times.
        """
        await self._client.close()
        self._is_initialized = False
        logger.info("LLMManager shut down.")

    # ═══════════════════════════════════════════════════════════════════
    #  CHAT (Non-Streaming)
    # ═══════════════════════════════════════════════════════════════════

    async def chat(
        self,
        message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Send a message and receive the full response.

        The message is added to memory, sent to the LLM with the full
        conversation context, and the response is also stored in memory.

        Args:
            message:     The user's input text.
            temperature: Override the default temperature for this call.
            max_tokens:  Override the default max_tokens for this call.

        Returns:
            The assistant's response text.

        Raises:
            LLMConnectionError:    If Ollama is unreachable.
            LLMTimeoutError:       If the request times out.
            LLMResponseParseError: If the response cannot be parsed.
        """
        self._ensure_initialized()

        # Add user message to memory
        self._memory.add_user_message(message)

        # Build generation config with overrides
        config = self._build_config(temperature, max_tokens)

        # Send full conversation context to LLM
        messages = self._memory.get_messages()

        logger.info(
            "Chat request  │  user_msg_length=%d  context_messages=%d  "
            "model=%s  temp=%.2f",
            len(message),
            len(messages),
            self._client.model,
            config.temperature,
        )

        response: LLMResponse = await self._client.generate(
            messages=messages,
            config=config,
        )

        # Store assistant response in memory
        self._memory.add_assistant_message(response.content)

        logger.info(
            "Chat response  │  length=%d  eval_count=%d  "
            "prompt_tokens=%d  duration_ms=%d",
            len(response.content),
            response.eval_count,
            response.prompt_eval_count,
            response.total_duration // 1_000_000 if response.total_duration else 0,
        )

        return response.content

    # ═══════════════════════════════════════════════════════════════════
    #  CHAT (Streaming)
    # ═══════════════════════════════════════════════════════════════════

    async def stream_chat(
        self,
        message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a message and yield response tokens as they arrive.

        The user message is added to memory before streaming begins.
        The full assistant response is assembled and added to memory
        after the stream completes.

        Args:
            message:     The user's input text.
            temperature: Override the default temperature for this call.
            max_tokens:  Override the default max_tokens for this call.

        Yields:
            Individual content tokens as strings.

        Raises:
            LLMConnectionError:    If Ollama is unreachable.
            LLMTimeoutError:       If the request times out.
        """
        self._ensure_initialized()

        # Add user message to memory
        self._memory.add_user_message(message)

        # Build generation config with overrides
        config = self._build_config(temperature, max_tokens)

        # Send full conversation context to LLM
        messages = self._memory.get_messages()

        logger.info(
            "Stream chat request  │  user_msg_length=%d  context_messages=%d  "
            "model=%s",
            len(message),
            len(messages),
            self._client.model,
        )

        # Collect full response while yielding tokens
        full_response_parts: list[str] = []

        async for token in self._client.generate_stream(
            messages=messages,
            config=config,
        ):
            full_response_parts.append(token)
            yield token

        # Store the complete assistant response in memory
        full_response = "".join(full_response_parts)
        self._memory.add_assistant_message(full_response)

        logger.info(
            "Stream chat complete  │  response_length=%d  tokens=%d",
            len(full_response),
            len(full_response_parts),
        )

    # ═══════════════════════════════════════════════════════════════════
    #  HEALTH CHECK
    # ═══════════════════════════════════════════════════════════════════

    async def health_check(self) -> bool:
        """
        Check whether Ollama is running and responsive.

        Returns:
            ``True`` if the server is healthy, ``False`` otherwise.
        """
        return await self._client.health_check()

    # ═══════════════════════════════════════════════════════════════════
    #  MODEL MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════

    async def change_model(self, model_name: str) -> None:
        """
        Switch the active LLM model at runtime.

        Verifies the new model is available before switching.
        The conversation memory is preserved across model changes.

        Args:
            model_name: The new model identifier (e.g. ``qwen3:8b``).

        Raises:
            LLMModelNotFoundError: If the model is not available.
        """
        # Verify model exists
        models = await self._client.list_models()
        if model_name not in models:
            raise LLMModelNotFoundError(
                f"Model '{model_name}' is not available. "
                f"Available models: {models}. "
                f"Run: ollama pull {model_name}"
            )

        old_model = self._client.model
        self._client.change_model(model_name)
        logger.info("Model changed  │  %s → %s", old_model, model_name)

    # ═══════════════════════════════════════════════════════════════════
    #  MEMORY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════

    def clear_memory(self) -> None:
        """
        Clear the conversation history.

        The system prompt is preserved. A new session ID is generated.
        """
        self._memory.clear()
        logger.info("Conversation memory cleared.")

    def save_history(self, filepath: str | Path) -> None:
        """
        Save the conversation history to a JSON file.

        Args:
            filepath: Path to the output JSON file. Parent directories
                      are created automatically if they don't exist.
        """
        self._memory.save_to_file(filepath)
        logger.info("History saved  │  path=%s", filepath)

    def load_history(self, filepath: str | Path) -> None:
        """
        Load a conversation history from a JSON file.

        Replaces the current memory with the loaded conversation.
        The system prompt from the file takes precedence.

        Args:
            filepath: Path to the JSON file to load.

        Raises:
            FileNotFoundError:    If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        self._memory = ConversationMemory.load_from_file(filepath)
        logger.info(
            "History loaded  │  path=%s  session=%s  messages=%d",
            filepath,
            self._memory.session_id,
            self._memory.total_count,
        )

    # ═══════════════════════════════════════════════════════════════════
    #  INTERNAL HELPERS
    # ═══════════════════════════════════════════════════════════════════

    def _ensure_initialized(self) -> None:
        """
        Guard that raises if the manager is not initialized.

        Raises:
            LLMConnectionError: If ``initialize()`` has not been called.
        """
        if not self._is_initialized:
            raise LLMConnectionError(
                "LLMManager is not initialized. Call await manager.initialize() first."
            )

    def _build_config(
        self,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GenerationConfig:
        """
        Build a GenerationConfig with optional overrides.

        Args:
            temperature: Override temperature (uses default if ``None``).
            max_tokens:  Override max_tokens (uses default if ``None``).

        Returns:
            A ``GenerationConfig`` with the merged settings.
        """
        return GenerationConfig(
            temperature=temperature if temperature is not None else self._default_config.temperature,
            max_tokens=max_tokens if max_tokens is not None else self._default_config.max_tokens,
            top_p=self._default_config.top_p,
            top_k=self._default_config.top_k,
            stop=self._default_config.stop,
        )

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"LLMManager(model={self._client.model!r}, "
            f"initialized={self._is_initialized}, "
            f"memory={self._memory.total_count} msgs)"
        )
