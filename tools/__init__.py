"""
Tools Module — System, file, and OS utilities for the agent.
=============================================================

Provides safe, managed access to the host operating system. All
tools are funneled through the ``ToolManager`` which handles logging,
timing, and exception management.

Quick Start::

    from tools import ToolManager

    manager = ToolManager()
    
    # Run a terminal command
    result = manager.execute("terminal.run", "echo Hello World")
    
    # Read a file
    content = manager.execute("file.read", "config.json")

Public API:
    - ToolManager         — The central orchestrator
    - ToolExecutionLog    — History of tool executions
    - FileTools           — FS operations
    - TerminalTools       — Shell command execution
    - ClipboardTools      — OS clipboard (Windows native)
    - SystemTools         — CPU/RAM/Disk metrics
    - ProcessTools        — Running process management
"""

from tools.tool_manager import ToolManager, ToolExecutionLog
from tools.file_tools import FileTools
from tools.terminal_tools import TerminalTools, CommandResult
from tools.clipboard_tools import ClipboardTools
from tools.system_tools import SystemTools, SystemInfo
from tools.process_tools import ProcessTools, ProcessInfo

__all__ = [
    "ToolManager",
    "ToolExecutionLog",
    "FileTools",
    "TerminalTools",
    "CommandResult",
    "ClipboardTools",
    "SystemTools",
    "SystemInfo",
    "ProcessTools",
    "ProcessInfo",
]
