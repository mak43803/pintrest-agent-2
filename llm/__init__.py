"""
LLM Module — Local LLM integration via Ollama REST API.
=========================================================

Provides a complete interface to a locally-running Ollama server
with Qwen 3 (or any supported model). Handles connectivity,
streaming, conversation memory, prompt management, and persistence.

Quick Start::

    from llm import LLMManager

    manager = LLMManager()
    await manager.initialize()

    response = await manager.chat("Hello, what can you do?")
    print(response)

    async for token in manager.stream_chat("Search for earbuds"):
        print(token, end="", flush=True)

    await manager.shutdown()

Public API:
    - LLMManager         — High-level orchestrator (start here)
    - OllamaClient       — Low-level HTTP client
    - ConversationMemory  — Message history & persistence
    - PromptManager      — Prompt template management
    - LLMResponse        — Structured response dataclass
    - GenerationConfig   — Generation parameter dataclass
"""

from llm.chat import LLMManager
from llm.llm import GenerationConfig, LLMResponse, OllamaClient
from llm.memory import ConversationMemory
from llm.prompt_manager import PromptManager

__all__ = [
    "LLMManager",
    "OllamaClient",
    "ConversationMemory",
    "PromptManager",
    "LLMResponse",
    "GenerationConfig",
]
