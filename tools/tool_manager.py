"""
Tool Manager — Unified gateway for all agent tooling.
======================================================

The ToolManager orchestrates all sub-tools (File, Terminal, System, etc.)
and provides a unified interface. It wraps every tool execution to automatically
log performance metrics (execution time), handle exceptions gracefully,
and maintain an execution history.

Usage::

    from tools.tool_manager import ToolManager
    
    manager = ToolManager()
    result = manager.execute("terminal.run_command", command="ping google.com")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from tools.clipboard_tools import ClipboardTools
from tools.file_tools import FileTools
from tools.process_tools import ProcessTools
from tools.system_tools import SystemTools
from tools.terminal_tools import TerminalTools

logger = logging.getLogger("pinterest_agent.tools.manager")


@dataclass
class ToolExecutionLog:
    """Record of a single tool execution."""
    tool_name: str
    args: dict[str, Any]
    kwargs: dict[str, Any]
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class ToolManager:
    """
    Central orchestrator for all agent tools.
    
    Provides a dispatch mechanism to run tools dynamically by name,
    while enforcing logging, timing, and error handling.
    """

    def __init__(self) -> None:
        self._history: list[ToolExecutionLog] = []
        
        # Registry mapping string names to callable methods
        self._registry: dict[str, Callable[..., Any]] = {
            # File Tools
            "file.read": FileTools.read_file,
            "file.write": FileTools.write_file,
            "file.delete": FileTools.delete_file,
            "file.move": FileTools.move_file,
            "file.copy": FileTools.copy_file,
            "file.rename": FileTools.rename_file,
            "file.mkdir": FileTools.create_folder,
            
            # Terminal Tools
            "terminal.run": TerminalTools.run_command,
            
            # Clipboard Tools
            "clipboard.copy": ClipboardTools.copy,
            "clipboard.paste": ClipboardTools.paste,
            "clipboard.clear": ClipboardTools.clear,
            
            # System Tools
            "system.cpu": SystemTools.get_cpu_usage,
            "system.ram": SystemTools.get_ram_usage,
            "system.disk": SystemTools.get_disk_usage,
            "system.os": SystemTools.get_os_info,
            "system.snapshot": SystemTools.get_full_snapshot,
            
            # Process Tools
            "process.list": ProcessTools.list_processes,
            "process.kill": ProcessTools.kill_process,
        }
        
        logger.info("ToolManager initialized  │  Registered %d tools", len(self._registry))

    # ── Core Dispatcher ────────────────────────────────────────────────

    def execute(self, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        """
        Execute a registered tool by name.

        Wraps the call in a timing and exception-handling block.
        All executions are recorded in the internal history.

        Args:
            tool_name: The dot-separated name of the tool (e.g. ``"file.read"``).
            *args:     Positional arguments for the underlying tool.
            **kwargs:  Keyword arguments for the underlying tool.

        Returns:
            The result of the tool execution.
            
        Raises:
            ValueError: If the tool_name is not registered.
            Exception:  Re-raises any exception thrown by the tool, after logging it.
        """
        if tool_name not in self._registry:
            error_msg = f"Tool '{tool_name}' is not registered."
            logger.error(error_msg)
            raise ValueError(error_msg)

        func = self._registry[tool_name]
        
        log_entry = ToolExecutionLog(
            tool_name=tool_name,
            args=dict(enumerate(args)),
            kwargs=kwargs,
        )
        
        logger.debug("Executing tool  │  name=%s", tool_name)
        start_time = time.perf_counter()

        try:
            # Run the actual tool logic
            result = func(*args, **kwargs)
            
            # Record success
            log_entry.result = result
            return result
            
        except Exception as exc:
            # Record failure
            error_msg = f"{type(exc).__name__}: {exc}"
            log_entry.error = error_msg
            logger.error("Tool execution failed  │  name=%s  error=%s", tool_name, error_msg)
            raise
            
        finally:
            # Calculate duration regardless of success/failure
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            log_entry.execution_time_ms = round(duration_ms, 2)
            
            self._history.append(log_entry)
            
            logger.info(
                "Tool finished  │  name=%s  duration=%.2fms  success=%s",
                tool_name,
                log_entry.execution_time_ms,
                log_entry.error is None
            )

    # ── Introspection ──────────────────────────────────────────────────

    def get_available_tools(self) -> list[str]:
        """Return a list of all registered tool names."""
        return sorted(list(self._registry.keys()))

    def get_execution_history(self) -> list[ToolExecutionLog]:
        """Return the log of all tools executed during this session."""
        return list(self._history)
