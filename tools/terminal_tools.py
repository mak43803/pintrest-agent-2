"""
Terminal Tools — Shell command execution for the agent.
========================================================

Allows the agent to execute shell commands securely. Captures
stdout, stderr, and supports execution timeouts and working directories.

Usage::

    from tools.terminal_tools import TerminalTools
    
    result = TerminalTools.run_command("pip install requests", timeout=30)
    print(result.stdout)
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("pinterest_agent.tools.terminal")


@dataclass
class CommandResult:
    """The result of a terminal command execution."""
    command: str
    return_code: int
    stdout: str
    stderr: str
    
    @property
    def is_success(self) -> bool:
        """Return True if the command exited with code 0."""
        return self.return_code == 0


class TerminalTools:
    """Operations for executing terminal/shell commands."""

    @staticmethod
    def run_command(
        command: str,
        cwd: str | Path | None = None,
        timeout: int = 60,
    ) -> CommandResult:
        """
        Execute a shell command.

        Args:
            command: The command string to execute.
            cwd:     Optional working directory.
            timeout: Maximum execution time in seconds.

        Returns:
            A ``CommandResult`` containing exit code, stdout, and stderr.
            
        Raises:
            subprocess.TimeoutExpired: If the command exceeds the timeout.
        """
        work_dir = str(cwd) if cwd else None
        logger.info("Executing command  │  cmd='%s'  cwd=%s", command, work_dir)
        
        try:
            # We use shell=True to allow complex commands (pipes, redirects)
            # which is typical for an AI agent's terminal tool.
            process = subprocess.run(
                command,
                cwd=work_dir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            result = CommandResult(
                command=command,
                return_code=process.returncode,
                stdout=process.stdout.strip(),
                stderr=process.stderr.strip()
            )
            
            if not result.is_success:
                logger.warning(
                    "Command failed  │  code=%d  stderr=%s",
                    result.return_code,
                    result.stderr[:100]
                )
                
            return result

        except subprocess.TimeoutExpired as exc:
            logger.error("Command timed out  │  timeout=%ds", timeout)
            raise
        except Exception as exc:
            logger.error("Command execution error  │  error=%s", exc)
            raise
