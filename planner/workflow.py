"""
Workflow — Ordered step sequences with checkpoint and resume support.
======================================================================

A Workflow is a named sequence of ``WorkflowStep`` objects. Each step
represents an atomic action (e.g. "download_image", "generate_title",
"upload_pin"). Workflows are:

    • **Ordered**    — steps execute sequentially.
    • **Resumable**  — current step is checkpointed to SQLite; on
                       restart the workflow resumes from the last
                       incomplete step.
    • **Observable** — every step transition is logged.
    • **Extensible** — define new workflows by composing step lists.

Step Lifecycle:
    PENDING → RUNNING → COMPLETED
                     ↘ FAILED → (retry or skip)

Usage::

    from planner.workflow import Workflow, WorkflowStep

    steps = [
        WorkflowStep(name="download_image", handler="browser.download"),
        WorkflowStep(name="generate_title", handler="llm.generate"),
        WorkflowStep(name="upload_pin",     handler="browser.upload"),
    ]
    wf = Workflow(name="pin_product", steps=steps)

    # Execute (or resume)
    for step in wf.pending_steps():
        wf.start_step(step.name)
        ...
        wf.complete_step(step.name)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable

logger = logging.getLogger("pinterest_agent.planner.workflow")


# ═══════════════════════════════════════════════════════════════════════
# Step Status
# ═══════════════════════════════════════════════════════════════════════

class StepStatus(str, Enum):
    """Status of an individual workflow step."""
    PENDING   = "Pending"
    RUNNING   = "Running"
    COMPLETED = "Completed"
    FAILED    = "Failed"
    SKIPPED   = "Skipped"

    def __str__(self) -> str:
        return self.value


# ═══════════════════════════════════════════════════════════════════════
# Workflow Step
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class WorkflowStep:
    """
    A single atomic step within a workflow.

    Attributes:
        name:        Unique step identifier within the workflow.
        handler:     Dotted path or key identifying the handler to call.
        description: Human-readable description of what this step does.
        status:      Current step status.
        result:      Result data from execution (if completed).
        error:       Error message (if failed).
        started_at:  When execution began.
        finished_at: When execution ended.
        retries:     Number of retry attempts for this step.
        max_retries: Maximum retries before marking as Failed.
        metadata:    Arbitrary key-value data for the handler.
    """
    name: str
    handler: str = ""
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    retries: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Return ``True`` if the step has finished (success or skip)."""
        return self.status in {StepStatus.COMPLETED, StepStatus.SKIPPED}

    @property
    def is_failed(self) -> bool:
        """Return ``True`` if the step has failed."""
        return self.status == StepStatus.FAILED

    @property
    def is_retryable(self) -> bool:
        """Return ``True`` if the step can be retried."""
        return self.status == StepStatus.FAILED and self.retries < self.max_retries

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "name": self.name,
            "handler": self.handler,
            "description": self.description,
            "status": self.status.value,
            "error": self.error,
            "retries": self.retries,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


# ═══════════════════════════════════════════════════════════════════════
# Workflow
# ═══════════════════════════════════════════════════════════════════════

def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Workflow:
    """
    An ordered sequence of steps with checkpoint/resume support.

    Tracks execution progress through the step list and provides
    methods for starting, completing, failing, and skipping steps.
    The current step index can be persisted for crash recovery.

    Args:
        name:  Workflow identifier (e.g. ``"pin_product"``).
        steps: Ordered list of ``WorkflowStep`` objects.
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(self, name: str, steps: list[WorkflowStep] | None = None) -> None:
        self._name = name
        self._steps: list[WorkflowStep] = steps or []
        self._current_index: int = 0
        self._created_at: str = _utc_now()

        logger.info(
            "Workflow created  │  name=%s  steps=%d",
            self._name,
            len(self._steps),
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return self._name

    @property
    def steps(self) -> list[WorkflowStep]:
        """Return a copy of the step list."""
        return list(self._steps)

    @property
    def step_count(self) -> int:
        """Return the total number of steps."""
        return len(self._steps)

    @property
    def current_step(self) -> WorkflowStep | None:
        """Return the current step, or ``None`` if the workflow is done."""
        if 0 <= self._current_index < len(self._steps):
            return self._steps[self._current_index]
        return None

    @property
    def current_step_name(self) -> str:
        """Return the name of the current step, or empty string."""
        step = self.current_step
        return step.name if step else ""

    @property
    def current_index(self) -> int:
        """Return the 0-based index of the current step."""
        return self._current_index

    @property
    def is_complete(self) -> bool:
        """Return ``True`` if all steps are complete or skipped."""
        return all(s.is_complete for s in self._steps)

    @property
    def is_failed(self) -> bool:
        """Return ``True`` if any step has permanently failed."""
        return any(
            s.is_failed and not s.is_retryable for s in self._steps
        )

    @property
    def progress(self) -> float:
        """Return completion percentage (0.0 to 100.0)."""
        if not self._steps:
            return 100.0
        completed = sum(1 for s in self._steps if s.is_complete)
        return round((completed / len(self._steps)) * 100.0, 1)

    @property
    def completed_count(self) -> int:
        """Return the number of completed steps."""
        return sum(1 for s in self._steps if s.is_complete)

    # ── Step Management ────────────────────────────────────────────────

    def add_step(self, step: WorkflowStep) -> None:
        """
        Append a step to the workflow.

        Args:
            step: The step to add.
        """
        self._steps.append(step)
        logger.debug("Step added  │  workflow=%s  step=%s", self._name, step.name)

    def pending_steps(self) -> list[WorkflowStep]:
        """Return all steps that have not yet completed."""
        return [s for s in self._steps if not s.is_complete]

    def get_step(self, name: str) -> WorkflowStep | None:
        """
        Find a step by name.

        Args:
            name: The step identifier.

        Returns:
            The ``WorkflowStep``, or ``None`` if not found.
        """
        for step in self._steps:
            if step.name == name:
                return step
        return None

    # ── Step Lifecycle ─────────────────────────────────────────────────

    def start_step(self, name: str) -> WorkflowStep:
        """
        Mark a step as Running and record the start time.

        Args:
            name: The step identifier.

        Returns:
            The updated ``WorkflowStep``.

        Raises:
            ValueError: If the step is not found.
        """
        step = self._require_step(name)
        step.status = StepStatus.RUNNING
        step.started_at = _utc_now()
        step.error = None

        logger.info(
            "Step started  │  workflow=%s  step=%s  index=%d/%d",
            self._name,
            name,
            self._step_index(name) + 1,
            len(self._steps),
        )
        return step

    def complete_step(self, name: str, result: Any = None) -> WorkflowStep:
        """
        Mark a step as Completed and advance the workflow.

        Args:
            name:   The step identifier.
            result: Optional result data from execution.

        Returns:
            The updated ``WorkflowStep``.
        """
        step = self._require_step(name)
        step.status = StepStatus.COMPLETED
        step.finished_at = _utc_now()
        step.result = result

        # Advance to next step
        idx = self._step_index(name)
        if idx is not None and idx >= self._current_index:
            self._current_index = idx + 1

        logger.info(
            "Step completed  │  workflow=%s  step=%s  progress=%.1f%%",
            self._name,
            name,
            self.progress,
        )
        return step

    def fail_step(self, name: str, error: str) -> WorkflowStep:
        """
        Mark a step as Failed with an error message.

        Args:
            name:  The step identifier.
            error: Error description.

        Returns:
            The updated ``WorkflowStep``.
        """
        step = self._require_step(name)
        step.status = StepStatus.FAILED
        step.finished_at = _utc_now()
        step.error = error
        step.retries += 1

        logger.error(
            "Step failed  │  workflow=%s  step=%s  error=%s  retries=%d/%d",
            self._name,
            name,
            error[:80],
            step.retries,
            step.max_retries,
        )
        return step

    def skip_step(self, name: str, reason: str = "") -> WorkflowStep:
        """
        Mark a step as Skipped and advance the workflow.

        Args:
            name:   The step identifier.
            reason: Why the step was skipped.

        Returns:
            The updated ``WorkflowStep``.
        """
        step = self._require_step(name)
        step.status = StepStatus.SKIPPED
        step.finished_at = _utc_now()
        step.error = reason or "Skipped"

        # Advance to next step
        idx = self._step_index(name)
        if idx is not None and idx >= self._current_index:
            self._current_index = idx + 1

        logger.info(
            "Step skipped  │  workflow=%s  step=%s  reason=%s",
            self._name,
            name,
            reason,
        )
        return step

    def retry_step(self, name: str) -> WorkflowStep:
        """
        Reset a failed step back to Pending for retry.

        Args:
            name: The step identifier.

        Returns:
            The updated ``WorkflowStep``.

        Raises:
            ValueError: If the step is not retryable.
        """
        step = self._require_step(name)
        if not step.is_retryable:
            raise ValueError(
                f"Step '{name}' is not retryable "
                f"(status={step.status.value}, retries={step.retries}/{step.max_retries})"
            )

        step.status = StepStatus.PENDING
        step.error = None
        step.finished_at = None

        logger.info(
            "Step reset for retry  │  workflow=%s  step=%s  attempt=%d/%d",
            self._name,
            name,
            step.retries,
            step.max_retries,
        )
        return step

    # ── Resume Support ─────────────────────────────────────────────────

    def resume_from(self, step_name: str) -> None:
        """
        Set the workflow to resume from a specific step.

        Used after loading checkpoint data from the database.

        Args:
            step_name: The name of the step to resume from.

        Raises:
            ValueError: If the step is not found.
        """
        idx = self._step_index(step_name)
        if idx is None:
            raise ValueError(f"Step '{step_name}' not found in workflow '{self._name}'.")

        self._current_index = idx
        logger.info(
            "Workflow resuming  │  name=%s  from_step=%s  index=%d",
            self._name,
            step_name,
            idx,
        )

    # ── Serialization ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the workflow to a dictionary."""
        return {
            "name": self._name,
            "current_index": self._current_index,
            "progress": self.progress,
            "is_complete": self.is_complete,
            "is_failed": self.is_failed,
            "created_at": self._created_at,
            "steps": [s.to_dict() for s in self._steps],
        }

    # ── Internal ───────────────────────────────────────────────────────

    def _require_step(self, name: str) -> WorkflowStep:
        """Look up a step by name or raise ValueError."""
        step = self.get_step(name)
        if step is None:
            raise ValueError(
                f"Step '{name}' not found in workflow '{self._name}'."
            )
        return step

    def _step_index(self, name: str) -> int | None:
        """Return the 0-based index of a step, or None."""
        for i, step in enumerate(self._steps):
            if step.name == name:
                return i
        return None

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Workflow(name={self._name!r}, "
            f"steps={len(self._steps)}, "
            f"progress={self.progress}%)"
        )

    def __len__(self) -> int:
        return len(self._steps)


# ═══════════════════════════════════════════════════════════════════════
# Pre-built Workflow Templates
# ═══════════════════════════════════════════════════════════════════════

def create_pin_product_workflow() -> Workflow:
    """
    Create the standard workflow for pinning a product.

    Steps:
        1. download_image   — Download the product image
        2. generate_title   — Generate a pin title via LLM
        3. generate_desc    — Generate a pin description via LLM
        4. create_pin       — Upload the pin to Pinterest
        5. verify_pin       — Verify the pin was created successfully

    Returns:
        A ``Workflow`` instance with all steps configured.
    """
    steps = [
        WorkflowStep(
            name="download_image",
            handler="browser.download_image",
            description="Download the product image to local storage.",
        ),
        WorkflowStep(
            name="generate_title",
            handler="llm.generate_title",
            description="Generate an SEO-optimized pin title via LLM.",
        ),
        WorkflowStep(
            name="generate_description",
            handler="llm.generate_description",
            description="Generate an engaging pin description via LLM.",
        ),
        WorkflowStep(
            name="create_pin",
            handler="browser.create_pin",
            description="Upload the pin to Pinterest with image and metadata.",
        ),
        WorkflowStep(
            name="verify_pin",
            handler="browser.verify_pin",
            description="Verify the pin was created successfully on the board.",
        ),
    ]

    return Workflow(name="pin_product", steps=steps)
