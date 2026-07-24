"""
Base Tool - Abstract base class for all agent tools.

Defines the interface that every tool must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    data: Any = None
    error: str | None = None


class BaseTool(ABC):
    """
    Abstract base class for all tools.

    Every tool must define its name, description, parameter schema,
    and an async execute method.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        """JSON Schema describing the tool's input parameters."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given parameters."""
        ...
