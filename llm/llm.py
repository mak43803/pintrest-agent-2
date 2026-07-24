"""
LLM — Ollama REST API client for local LLM inference.
=======================================================

Production-grade client for the Ollama REST API that provides:

    • Health checking — verify Ollama is running and model is available
    • Auto-reconnect — retry with backoff when Ollama becomes unavailable
    • Streaming — token-by-token response via async generators
    • Non-streaming — full response in a single call
    • Configurable — temperature, max_tokens, top_p, timeout
    • Model management — switch models at runtime
    • Full logging — every request/response lifecycle event

Architecture:
    This is the lowest-level module in the LLM stack. It knows nothing
    about conversation history, prompts, or memory — those are handled
    by ``chat.py`` and ``memory.py`` which compose on top of this client.

Ollama REST API Endpoints Used:
    - ``GET  /``                  → health check
    - ``GET  /api/tags``          → list available models
    - ``POST /api/chat``          → chat completion (streaming & non-streaming)

Usage::

    from llm.llm import OllamaClient

    client = OllamaClient(base_url="http://localhost:11434", model="qwen3:8b")
    await client.initialize()

    # Non-streaming
    response = await client.generate(messages=[...])

    # Streaming
    async for token in client.generate_stream(messages=[...]):
        print(token, end="", flush=True)

    await client.close()
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

import aiohttp

from utils.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMResponseParseError,
    LLMTimeoutError,
)

logger = logging.getLogger("pinterest_agent.llm")


# ═══════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LLMResponse:
    """
    Structured response from an Ollama chat completion.

    Attributes:
        content:          The generated text content.
        model:            Model that produced the response.
        total_duration:   Total request duration in nanoseconds.
        prompt_eval_count: Number of tokens in the prompt.
        eval_count:       Number of tokens generated.
        done:             Whether generation is complete.
    """
    content: str
    model: str = ""
    total_duration: int = 0
    prompt_eval_count: int = 0
    eval_count: int = 0
    done: bool = True


@dataclass
class GenerationConfig:
    """
    Generation parameters passed to the Ollama API.

    Attributes:
        temperature: Sampling temperature (0.0–2.0).
        max_tokens:  Maximum tokens to generate (``num_predict``).
        top_p:       Nucleus sampling probability.
        top_k:       Top-k sampling (0 = disabled).
        stop:        List of stop sequences.
    """
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    top_k: int = 40
    stop: list[str] = field(default_factory=list)

    def to_options(self) -> dict[str, Any]:
        """Convert to the Ollama ``options`` dict format."""
        opts: dict[str, Any] = {
            "temperature": self.temperature,
            "num_predict": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }
        if self.stop:
            opts["stop"] = self.stop
        return opts


# ═══════════════════════════════════════════════════════════════════════
# Ollama Client
# ═══════════════════════════════════════════════════════════════════════

class OllamaClient:
    """
    Async HTTP client for the Ollama REST API.

    Manages its own ``aiohttp.ClientSession`` and provides both
    streaming and non-streaming chat completion methods.

    Args:
        base_url:            Ollama server URL (e.g. ``http://localhost:11434``).
        model:               Default model name (e.g. ``qwen3:8b``).
        timeout_seconds:     Request timeout in seconds.
        max_retries:         Maximum retry attempts on transient failures.
        retry_delay_seconds: Delay between retries (doubles each attempt).
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:8b",
        timeout_seconds: int = 120,
        max_retries: int = 3,
        retry_delay_seconds: float = 2.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self._session: aiohttp.ClientSession | None = None
        self._is_initialized = False

        logger.debug(
            "OllamaClient created  │  url=%s  model=%s  timeout=%ds  retries=%d",
            self._base_url,
            self._model,
            self._timeout_seconds,
            self._max_retries,
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def base_url(self) -> str:
        """Return the Ollama server base URL."""
        return self._base_url

    @property
    def model(self) -> str:
        """Return the currently active model name."""
        return self._model

    @property
    def is_initialized(self) -> bool:
        """Return whether the client has been initialized."""
        return self._is_initialized

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """
        Initialize the HTTP session and verify connectivity.

        Creates the ``aiohttp.ClientSession``, checks that Ollama is
        running, and verifies the configured model is available.

        Raises:
            LLMConnectionError:   If Ollama is unreachable.
            LLMModelNotFoundError: If the model is not pulled.
        """
        if self._is_initialized and self._session and not self._session.closed:
            logger.debug("OllamaClient already initialized.")
            return

        timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
        self._session = aiohttp.ClientSession(timeout=timeout)

        # Verify Ollama is running
        if not await self.health_check():
            await self.close()
            raise LLMConnectionError(
                f"Ollama server is not reachable at {self._base_url}"
            )

        # Verify model is available
        if not await self._model_exists(self._model):
            await self.close()
            raise LLMModelNotFoundError(
                f"Model '{self._model}' is not available. "
                f"Run: ollama pull {self._model}"
            )

        self._is_initialized = True
        logger.info(
            "OllamaClient initialized  │  url=%s  model=%s",
            self._base_url,
            self._model,
        )

    async def close(self) -> None:
        """
        Close the HTTP session and release resources.

        Safe to call multiple times.
        """
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("OllamaClient session closed.")
        self._is_initialized = False

    # ── Health & Model Checks ──────────────────────────────────────────

    async def health_check(self) -> bool:
        """
        Check whether the Ollama server is running and responsive.

        Returns:
            ``True`` if the server responds, ``False`` otherwise.
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/") as resp:
                is_healthy = resp.status == 200
                if is_healthy:
                    logger.debug("Ollama health check passed.")
                else:
                    logger.warning(
                        "Ollama health check failed  │  status=%d", resp.status
                    )
                return is_healthy
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("Ollama health check failed  │  error=%s", exc)
            return False

    async def _model_exists(self, model_name: str) -> bool:
        """
        Check whether a model is available in Ollama.

        Args:
            model_name: The model identifier (e.g. ``qwen3:8b``).

        Returns:
            ``True`` if the model is pulled and ready.
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/api/tags") as resp:
                if resp.status != 200:
                    logger.warning("Failed to list models  │  status=%d", resp.status)
                    return False

                data = await resp.json()
                models = data.get("models", [])
                available = [m.get("name", "") for m in models]

                exists = model_name in available
                if not exists:
                    logger.warning(
                        "Model '%s' not found  │  available=%s",
                        model_name,
                        available,
                    )
                else:
                    logger.debug("Model '%s' is available.", model_name)
                return exists

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.error("Failed to check model existence  │  error=%s", exc)
            return False

    async def list_models(self) -> list[str]:
        """
        List all models available in Ollama.

        Returns:
            A list of model name strings.
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/api/tags") as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return [m.get("name", "") for m in data.get("models", [])]
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return []

    # ── Generation (Non-Streaming) ─────────────────────────────────────

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: GenerationConfig | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """
        Send a chat completion request and return the full response.

        Args:
            messages: List of message dicts with ``role`` and ``content``.
            config:   Generation parameters (uses defaults if ``None``).
            model:    Override model for this request.

        Returns:
            An ``LLMResponse`` with the generated content.

        Raises:
            LLMConnectionError:    If Ollama is unreachable after retries.
            LLMTimeoutError:       If the request times out.
            LLMResponseParseError: If the response cannot be parsed.
        """
        config = config or GenerationConfig()
        target_model = model or self._model

        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": config.to_options(),
        }

        data = await self._post_with_retry("/api/chat", payload)

        try:
            message = data.get("message", {})
            return LLMResponse(
                content=message.get("content", ""),
                model=data.get("model", target_model),
                total_duration=data.get("total_duration", 0),
                prompt_eval_count=data.get("prompt_eval_count", 0),
                eval_count=data.get("eval_count", 0),
                done=data.get("done", True),
            )
        except (KeyError, TypeError) as exc:
            logger.error("Failed to parse LLM response  │  error=%s", exc)
            raise LLMResponseParseError(
                f"Cannot parse Ollama response: {exc}"
            ) from exc

    # ── Generation (Streaming) ─────────────────────────────────────────

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        config: GenerationConfig | None = None,
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a chat completion request and yield tokens as they arrive.

        Args:
            messages: List of message dicts with ``role`` and ``content``.
            config:   Generation parameters (uses defaults if ``None``).
            model:    Override model for this request.

        Yields:
            Individual content tokens as strings.

        Raises:
            LLMConnectionError:    If Ollama is unreachable after retries.
            LLMTimeoutError:       If the request times out.
            LLMResponseParseError: If a streamed chunk cannot be parsed.
        """
        config = config or GenerationConfig()
        target_model = model or self._model

        payload = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "options": config.to_options(),
        }

        session = await self._get_session()
        url = f"{self._base_url}/api/chat"

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise LLMConnectionError(
                            f"Ollama returned status {resp.status}: {body[:200]}"
                        )

                    async for line in resp.content:
                        if not line:
                            continue

                        try:
                            chunk = json.loads(line.decode("utf-8"))
                        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                            logger.warning("Skipping malformed chunk  │  error=%s", exc)
                            continue

                        message = chunk.get("message", {})
                        content = message.get("content", "")
                        if content:
                            yield content

                        if chunk.get("done", False):
                            logger.debug(
                                "Stream complete  │  model=%s  eval_count=%d",
                                chunk.get("model", target_model),
                                chunk.get("eval_count", 0),
                            )
                            return

                # If we reach here, stream ended without done=True
                return

            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning(
                    "Stream timeout (attempt %d/%d)  │  model=%s",
                    attempt,
                    self._max_retries,
                    target_model,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * attempt)

            except aiohttp.ClientError as exc:
                last_error = exc
                logger.warning(
                    "Stream connection error (attempt %d/%d)  │  error=%s",
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * attempt)

        # All retries exhausted
        if isinstance(last_error, asyncio.TimeoutError):
            raise LLMTimeoutError(
                f"Streaming request timed out after {self._max_retries} attempts"
            ) from last_error
        raise LLMConnectionError(
            f"Streaming request failed after {self._max_retries} attempts: {last_error}"
        ) from last_error

    # ── Model Management ───────────────────────────────────────────────

    def change_model(self, model_name: str) -> None:
        """
        Switch the active model.

        Args:
            model_name: New model identifier (e.g. ``qwen3:8b``).
        """
        old_model = self._model
        self._model = model_name
        logger.info("Model changed  │  %s → %s", old_model, model_name)

    # ── Internal Helpers ───────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Return the active session, creating a new one if closed.

        Implements auto-reconnect: if the session was closed (e.g. after
        a network failure), a fresh session is transparently created.

        Returns:
            An open ``aiohttp.ClientSession``.
        """
        if self._session is None or self._session.closed:
            logger.info("Recreating HTTP session (auto-reconnect).")
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _post_with_retry(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        POST to an Ollama endpoint with exponential-backoff retry.

        Args:
            endpoint: API path (e.g. ``/api/chat``).
            payload:  JSON request body.

        Returns:
            The parsed JSON response as a dict.

        Raises:
            LLMConnectionError: After all retries are exhausted.
            LLMTimeoutError:    If every attempt times out.
        """
        url = f"{self._base_url}{endpoint}"
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                session = await self._get_session()
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise LLMConnectionError(
                            f"Ollama returned status {resp.status}: {body[:200]}"
                        )

                    data = await resp.json()
                    logger.debug(
                        "POST %s succeeded  │  attempt=%d  model=%s",
                        endpoint,
                        attempt,
                        payload.get("model", "?"),
                    )
                    return data

            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning(
                    "Request timeout (attempt %d/%d)  │  endpoint=%s",
                    attempt,
                    self._max_retries,
                    endpoint,
                )

            except aiohttp.ClientError as exc:
                last_error = exc
                logger.warning(
                    "Connection error (attempt %d/%d)  │  endpoint=%s  error=%s",
                    attempt,
                    self._max_retries,
                    endpoint,
                    exc,
                )

            # Exponential backoff
            if attempt < self._max_retries:
                delay = self._retry_delay * attempt
                logger.debug("Retrying in %.1fs...", delay)
                await asyncio.sleep(delay)

        # All retries exhausted
        if isinstance(last_error, asyncio.TimeoutError):
            raise LLMTimeoutError(
                f"Request to {endpoint} timed out after {self._max_retries} attempts"
            ) from last_error
        raise LLMConnectionError(
            f"Request to {endpoint} failed after {self._max_retries} attempts: "
            f"{last_error}"
        ) from last_error

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"OllamaClient(url={self._base_url!r}, "
            f"model={self._model!r}, "
            f"initialized={self._is_initialized})"
        )
