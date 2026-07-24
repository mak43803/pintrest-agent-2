"""
Base Agent - Abstract base class for all agent implementations.

Provides the foundational interface and shared logic that all
concrete agent types must implement.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """
    Abstract base class defining the agent contract.

    All agent implementations must inherit from this class and
    implement the required abstract methods for the agent lifecycle.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._is_running = False

    @property
    def name(self) -> str:
        """Return the agent's identifier name."""
        return self._name

    @property
    def is_running(self) -> bool:
        """Return whether the agent is currently active."""
        return self._is_running

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the agent and all subsystems."""
        ...

    @abstractmethod
    async def run(self) -> None:
        """Start the main agent execution loop."""
        ...

    @abstractmethod
    async def step(self, user_input: str) -> Any:
        """Execute a single reasoning/action step."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shut down the agent and release resources."""
        ...
