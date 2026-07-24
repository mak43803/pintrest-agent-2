"""
Agent State - State management and lifecycle tracking for the agent.

Manages the agent's internal state machine, including transitions
between idle, planning, executing, and error states.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class AgentStatus(Enum):
    """Enumeration of possible agent states."""
    IDLE = auto()
    INITIALIZING = auto()
    PLANNING = auto()
    EXECUTING = auto()
    WAITING_FOR_INPUT = auto()
    ERROR = auto()
    SHUTTING_DOWN = auto()


@dataclass
class AgentState:
    """
    Immutable snapshot of the agent's current state.

    Attributes:
        status: Current agent lifecycle status.
        current_task: Description of the active task, if any.
        step_count: Total number of steps executed.
        error_message: Last error message, if in ERROR state.
        created_at: Timestamp when this state was created.
        metadata: Arbitrary key-value metadata.
    """
    status: AgentStatus = AgentStatus.IDLE
    current_task: str | None = None
    step_count: int = 0
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
