"""
State Machine — Finite state machine for task and planner lifecycle.
=====================================================================

Defines the ``PlannerState`` enumeration and the ``StateMachine``
class that governs legal state transitions. Every transition is
validated, logged, and can trigger optional callbacks.

States:
    IDLE       → The planner is inactive, waiting for work.
    PLANNING   → The planner is analysing tasks and building a plan.
    EXECUTING  → The planner is actively executing a workflow step.
    WAITING    → The planner is paused, waiting for external input.
    RETRYING   → A step failed and is being retried.
    COMPLETED  → The current task/workflow finished successfully.
    FAILED     → The current task/workflow terminated with an error.

Legal Transitions::

    IDLE       → PLANNING
    PLANNING   → EXECUTING, FAILED
    EXECUTING  → WAITING, RETRYING, COMPLETED, FAILED
    WAITING    → EXECUTING, FAILED
    RETRYING   → EXECUTING, FAILED
    COMPLETED  → IDLE
    FAILED     → IDLE, RETRYING

Design:
    - Transition table is defined as a class constant for clarity
    - Invalid transitions raise ``InvalidStateTransition``
    - History of all transitions is stored for debugging
    - Thread-safe via ``threading.Lock``
    - Callbacks can be registered per (from_state, to_state) pair
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable

logger = logging.getLogger("pinterest_agent.planner.state_machine")


# ═══════════════════════════════════════════════════════════════════════
# State Enumeration
# ═══════════════════════════════════════════════════════════════════════

class PlannerState(str, Enum):
    """
    Finite states for the planner lifecycle.

    Inherits ``str`` for clean serialization and logging.
    """
    IDLE       = "Idle"
    PLANNING   = "Planning"
    EXECUTING  = "Executing"
    WAITING    = "Waiting"
    RETRYING   = "Retrying"
    COMPLETED  = "Completed"
    FAILED     = "Failed"

    def __str__(self) -> str:
        return self.value


# ═══════════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════════

class InvalidStateTransition(Exception):
    """Raised when an illegal state transition is attempted."""

    def __init__(self, from_state: PlannerState, to_state: PlannerState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid state transition: {from_state.value} → {to_state.value}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Transition Record
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StateTransition:
    """
    Immutable record of a single state transition.

    Attributes:
        from_state:  The state before the transition.
        to_state:    The state after the transition.
        timestamp:   When the transition occurred (UTC).
        reason:      Optional human-readable reason for the transition.
    """
    from_state: PlannerState
    to_state: PlannerState
    timestamp: str
    reason: str = ""


# ═══════════════════════════════════════════════════════════════════════
# State Machine
# ═══════════════════════════════════════════════════════════════════════

# Type alias for transition callbacks
TransitionCallback = Callable[[PlannerState, PlannerState], None]


class StateMachine:
    """
    Thread-safe finite state machine with transition validation.

    Enforces the legal transition table, records full transition
    history, and supports optional callbacks on state changes.

    Args:
        initial_state: The starting state (default ``IDLE``).
    """

    # ── Legal Transition Table ─────────────────────────────────────────
    TRANSITIONS: dict[PlannerState, set[PlannerState]] = {
        PlannerState.IDLE:      {PlannerState.PLANNING},
        PlannerState.PLANNING:  {PlannerState.EXECUTING, PlannerState.FAILED},
        PlannerState.EXECUTING: {PlannerState.WAITING, PlannerState.RETRYING,
                                 PlannerState.COMPLETED, PlannerState.FAILED},
        PlannerState.WAITING:   {PlannerState.EXECUTING, PlannerState.FAILED},
        PlannerState.RETRYING:  {PlannerState.EXECUTING, PlannerState.FAILED},
        PlannerState.COMPLETED: {PlannerState.IDLE},
        PlannerState.FAILED:    {PlannerState.IDLE, PlannerState.RETRYING},
    }

    # ── Construction ───────────────────────────────────────────────────

    def __init__(self, initial_state: PlannerState = PlannerState.IDLE) -> None:
        self._state = initial_state
        self._lock = threading.Lock()
        self._history: list[StateTransition] = []
        self._callbacks: dict[tuple[PlannerState, PlannerState], list[TransitionCallback]] = {}

        logger.info("StateMachine initialized  │  state=%s", self._state.value)

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def state(self) -> PlannerState:
        """Return the current state (thread-safe read)."""
        with self._lock:
            return self._state

    @property
    def history(self) -> list[StateTransition]:
        """Return a copy of the full transition history."""
        with self._lock:
            return list(self._history)

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` if the current state is COMPLETED or FAILED."""
        return self._state in {PlannerState.COMPLETED, PlannerState.FAILED}

    @property
    def is_active(self) -> bool:
        """Return ``True`` if the machine is in an active (non-idle, non-terminal) state."""
        return self._state in {
            PlannerState.PLANNING,
            PlannerState.EXECUTING,
            PlannerState.WAITING,
            PlannerState.RETRYING,
        }

    # ── Transitions ────────────────────────────────────────────────────

    def transition_to(
        self,
        new_state: PlannerState,
        reason: str = "",
    ) -> None:
        """
        Transition to a new state.

        Args:
            new_state: The target state.
            reason:    Human-readable reason for the transition.

        Raises:
            InvalidStateTransition: If the transition is not legal.
        """
        with self._lock:
            old_state = self._state
            allowed = self.TRANSITIONS.get(old_state, set())

            if new_state not in allowed:
                logger.error(
                    "Invalid transition  │  %s → %s  │  allowed=%s",
                    old_state.value,
                    new_state.value,
                    {s.value for s in allowed},
                )
                raise InvalidStateTransition(old_state, new_state)

            # Record transition
            record = StateTransition(
                from_state=old_state,
                to_state=new_state,
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                reason=reason,
            )
            self._history.append(record)
            self._state = new_state

            logger.info(
                "State transition  │  %s → %s  │  reason=%s",
                old_state.value,
                new_state.value,
                reason or "(none)",
            )

        # Fire callbacks outside the lock to avoid deadlocks
        self._fire_callbacks(old_state, new_state)

    def can_transition_to(self, new_state: PlannerState) -> bool:
        """
        Check whether a transition to the given state is legal.

        Args:
            new_state: The target state to check.

        Returns:
            ``True`` if the transition is allowed.
        """
        with self._lock:
            allowed = self.TRANSITIONS.get(self._state, set())
            return new_state in allowed

    def reset(self) -> None:
        """
        Force-reset the state machine to ``IDLE``.

        Clears all history. Use only for error recovery or tests.
        """
        with self._lock:
            old_state = self._state
            self._state = PlannerState.IDLE
            self._history.clear()
            logger.warning(
                "StateMachine force-reset  │  %s → IDLE", old_state.value
            )

    # ── Callbacks ──────────────────────────────────────────────────────

    def on_transition(
        self,
        from_state: PlannerState,
        to_state: PlannerState,
        callback: TransitionCallback,
    ) -> None:
        """
        Register a callback for a specific transition.

        Args:
            from_state: The source state.
            to_state:   The target state.
            callback:   A callable ``(from_state, to_state) -> None``.
        """
        key = (from_state, to_state)
        self._callbacks.setdefault(key, []).append(callback)
        logger.debug(
            "Callback registered  │  %s → %s", from_state.value, to_state.value
        )

    def _fire_callbacks(
        self,
        from_state: PlannerState,
        to_state: PlannerState,
    ) -> None:
        """Fire all callbacks registered for this transition pair."""
        key = (from_state, to_state)
        for cb in self._callbacks.get(key, []):
            try:
                cb(from_state, to_state)
            except Exception as exc:
                logger.error(
                    "Transition callback error  │  %s → %s  │  error=%s",
                    from_state.value,
                    to_state.value,
                    exc,
                )

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"StateMachine(state={self._state.value!r}, "
            f"transitions={len(self._history)})"
        )
