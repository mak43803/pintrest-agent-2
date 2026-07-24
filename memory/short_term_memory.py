"""
Short-Term Memory — Tracks the active task context and execution history.
==========================================================================

Short-term memory stores temporary data needed during the execution
of the current task or workflow. When a task completes or fails,
relevant insights are transferred to Long-Term Memory, and the
short-term memory is cleared.

Features:
    • Current task metadata tracking
    • Step-by-step execution history
    • Temporary context variables
    • Automatic cleanup

Usage::

    from memory.short_term_memory import ShortTermMemory

    stm = ShortTermMemory()
    stm.set_context("current_product", "wireless_earbuds")
    stm.add_execution_step("download_image", "Success")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("pinterest_agent.memory.short_term")


@dataclass
class ExecutionStep:
    """Record of a single action taken during the current task."""
    step_name: str
    result: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ShortTermMemory:
    """
    In-memory store for the current active task context.
    """

    def __init__(self) -> None:
        self._context: dict[str, Any] = {}
        self._execution_history: list[ExecutionStep] = []
        self._active_task_id: int | None = None
        logger.info("ShortTermMemory initialized.")

    # ── Context Management ─────────────────────────────────────────────

    def set_context(self, key: str, value: Any) -> None:
        """Store a temporary variable."""
        self._context[key] = value
        logger.debug("Context set  │  %s = %s", key, value)

    def get_context(self, key: str, default: Any = None) -> Any:
        """Retrieve a temporary variable."""
        return self._context.get(key, default)

    def get_all_context(self) -> dict[str, Any]:
        """Return all context variables."""
        return dict(self._context)

    # ── Execution History ──────────────────────────────────────────────

    def add_execution_step(
        self,
        step_name: str,
        result: str,
        **metadata: Any,
    ) -> None:
        """Record the outcome of a workflow step."""
        step = ExecutionStep(step_name=step_name, result=result, metadata=metadata)
        self._execution_history.append(step)
        logger.debug("Execution step recorded  │  step=%s", step_name)

    def get_execution_history(self) -> list[ExecutionStep]:
        """Return the sequence of actions taken so far."""
        return list(self._execution_history)

    # ── Task Tracking ──────────────────────────────────────────────────

    def start_task(self, task_id: int) -> None:
        """Initialize memory for a new task."""
        self.clear()
        self._active_task_id = task_id
        logger.info("ShortTermMemory bound to task  │  task_id=%s", task_id)

    @property
    def active_task_id(self) -> int | None:
        """Return the ID of the currently tracked task."""
        return self._active_task_id

    # ── Cleanup ────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Wipe the short-term memory (usually at task boundary)."""
        self._context.clear()
        self._execution_history.clear()
        self._active_task_id = None
        logger.debug("ShortTermMemory cleared.")
