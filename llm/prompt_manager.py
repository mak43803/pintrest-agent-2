"""
Prompt Manager — Centralized prompt template management.
=========================================================

Handles loading, formatting, and validating prompt templates for
the LLM. Separates prompt content from application logic so that
prompts can be iterated independently of code changes.

Responsibilities:
    • Store and retrieve named prompt templates
    • Format templates with dynamic variables
    • Combine system prompt + task context + user input
    • Validate that all required placeholders are filled

Usage::

    from llm.prompt_manager import PromptManager

    pm = PromptManager()
    pm.register_template("search", "Search Pinterest for: {query}")

    formatted = pm.format("search", query="wireless earbuds")
    system = pm.get_system_prompt()
"""

from __future__ import annotations

import logging
import re
from typing import Any

from prompts.system_prompts import SYSTEM_PROMPT

logger = logging.getLogger("pinterest_agent.llm.prompt_manager")


class PromptManager:
    """
    Centralized manager for LLM prompt templates.

    Stores named templates and provides safe formatting with
    validation of required placeholders.

    Args:
        default_system_prompt: The default system prompt to use if
                               none is explicitly set.
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(self, default_system_prompt: str | None = None) -> None:
        self._system_prompt = default_system_prompt or SYSTEM_PROMPT
        self._templates: dict[str, str] = {}

        logger.info(
            "PromptManager created  │  system_prompt_length=%d",
            len(self._system_prompt),
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def system_prompt(self) -> str:
        """Return the current system prompt."""
        return self._system_prompt

    @property
    def template_names(self) -> list[str]:
        """Return a sorted list of registered template names."""
        return sorted(self._templates.keys())

    # ── System Prompt ──────────────────────────────────────────────────

    def get_system_prompt(self) -> str:
        """
        Return the active system prompt.

        Returns:
            The system prompt string.
        """
        return self._system_prompt

    def set_system_prompt(self, prompt: str) -> None:
        """
        Replace the active system prompt.

        Args:
            prompt: The new system prompt text.
        """
        self._system_prompt = prompt
        logger.info("System prompt updated  │  length=%d", len(prompt))

    # ── Template Registration ──────────────────────────────────────────

    def register_template(self, name: str, template: str) -> None:
        """
        Register a named prompt template.

        Templates use Python's ``str.format()`` syntax with named
        placeholders (e.g. ``{query}``, ``{board_name}``).

        Args:
            name:     Unique template identifier.
            template: The template string with ``{placeholder}`` variables.
        """
        self._templates[name] = template
        placeholders = self._extract_placeholders(template)
        logger.info(
            "Template registered  │  name=%s  placeholders=%s",
            name,
            placeholders,
        )

    def register_templates(self, templates: dict[str, str]) -> None:
        """
        Register multiple templates at once.

        Args:
            templates: Mapping of template names to template strings.
        """
        for name, template in templates.items():
            self.register_template(name, template)

    def get_template(self, name: str) -> str | None:
        """
        Retrieve a raw template by name.

        Args:
            name: The template identifier.

        Returns:
            The template string, or ``None`` if not found.
        """
        return self._templates.get(name)

    def has_template(self, name: str) -> bool:
        """
        Check whether a template is registered.

        Args:
            name: The template identifier.

        Returns:
            ``True`` if the template exists.
        """
        return name in self._templates

    # ── Formatting ─────────────────────────────────────────────────────

    def format(self, name: str, **kwargs: Any) -> str:
        """
        Format a registered template with the given variables.

        Args:
            name:    The template identifier.
            **kwargs: Values for the template placeholders.

        Returns:
            The formatted prompt string.

        Raises:
            KeyError: If the template name is not registered.
            KeyError: If a required placeholder is missing from kwargs.
        """
        template = self._templates.get(name)
        if template is None:
            raise KeyError(f"Prompt template '{name}' is not registered.")

        # Validate all placeholders are provided
        required = self._extract_placeholders(template)
        missing = required - set(kwargs.keys())
        if missing:
            raise KeyError(
                f"Missing placeholders for template '{name}': {missing}"
            )

        formatted = template.format(**kwargs)
        logger.debug(
            "Template formatted  │  name=%s  length=%d",
            name,
            len(formatted),
        )
        return formatted

    def format_raw(self, template: str, **kwargs: Any) -> str:
        """
        Format an arbitrary template string (not registered).

        Args:
            template: The template string.
            **kwargs: Values for placeholders.

        Returns:
            The formatted string.
        """
        return template.format(**kwargs)

    # ── Message Building ───────────────────────────────────────────────

    def build_messages(
        self,
        user_input: str,
        task_context: str | None = None,
        system_override: str | None = None,
    ) -> list[dict[str, str]]:
        """
        Construct a complete message list for an Ollama chat request.

        Assembles: system prompt → (optional task context) → user input.

        Args:
            user_input:      The user's message or question.
            task_context:    Optional task-specific context injected as
                             a system message between the main system
                             prompt and the user message.
            system_override: If provided, replaces the default system prompt
                             for this request only.

        Returns:
            A list of message dicts ready for the Ollama API.
        """
        messages: list[dict[str, str]] = []

        # System prompt
        system = system_override or self._system_prompt
        if system:
            messages.append({"role": "system", "content": system})

        # Task context (injected as additional system context)
        if task_context:
            messages.append({"role": "system", "content": task_context})

        # User input
        messages.append({"role": "user", "content": user_input})

        logger.debug(
            "Messages built  │  parts=%d  system=%s  task_ctx=%s",
            len(messages),
            bool(system),
            bool(task_context),
        )
        return messages

    # ── Internal ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_placeholders(template: str) -> set[str]:
        """
        Extract all ``{placeholder}`` names from a template string.

        Args:
            template: The template string to scan.

        Returns:
            A set of placeholder names.
        """
        return set(re.findall(r"\{(\w+)\}", template))

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"PromptManager(templates={len(self._templates)}, "
            f"system_prompt_length={len(self._system_prompt)})"
        )
