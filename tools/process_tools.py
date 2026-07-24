"""
Process Tools — Managing running system processes.
===================================================

Provides the ability to list running processes, find specific apps,
and gracefully terminate them. Used by the agent to ensure clean
environments (e.g., closing zombie browser processes).

Requires the ``psutil`` package.

Usage::

    from tools.process_tools import ProcessTools
    
    processes = ProcessTools.list_processes(name_filter="chrome")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger("pinterest_agent.tools.process")


@dataclass
class ProcessInfo:
    """Information about a running OS process."""
    pid: int
    name: str
    status: str
    memory_mb: float


class ProcessTools:
    """Operations for querying and managing OS processes."""

    @staticmethod
    def list_processes(name_filter: str = "") -> list[ProcessInfo]:
        """
        List currently running processes.

        Args:
            name_filter: Optional substring to filter process names.
                         Case-insensitive.

        Returns:
            A list of ``ProcessInfo`` objects.
        """
        if not HAS_PSUTIL:
            logger.warning("psutil not installed. Cannot list processes.")
            return []

        results: list[ProcessInfo] = []
        name_filter = name_filter.lower()

        # Iterate over all running process
        for proc in psutil.process_iter(['pid', 'name', 'status', 'memory_info']):
            try:
                info = proc.info
                name = str(info.get('name', ''))
                
                # Apply filter
                if name_filter and name_filter not in name.lower():
                    continue
                    
                # Convert bytes to MB
                mem = info.get('memory_info')
                mem_mb = mem.rss / (1024 * 1024) if mem else 0.0

                results.append(
                    ProcessInfo(
                        pid=info.get('pid', 0),
                        name=name,
                        status=str(info.get('status', 'unknown')),
                        memory_mb=round(mem_mb, 2),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        return results

    @staticmethod
    def kill_process(pid: int) -> bool:
        """
        Attempt to terminate a process by ID.

        Args:
            pid: The process ID to kill.

        Returns:
            True if the process was successfully terminated, False otherwise.
        """
        if not HAS_PSUTIL:
            logger.warning("psutil not installed. Cannot kill process.")
            return False

        try:
            proc = psutil.Process(pid)
            proc.terminate()
            
            # Wait up to 3 seconds for graceful exit
            proc.wait(timeout=3)
            logger.info("Process terminated  │  pid=%d  name=%s", pid, proc.name())
            return True
            
        except psutil.TimeoutExpired:
            # Force kill if termination timed out
            proc.kill()
            logger.warning("Process forcefully killed  │  pid=%d", pid)
            return True
            
        except psutil.NoSuchProcess:
            logger.warning("Process not found  │  pid=%d", pid)
            return False
            
        except psutil.AccessDenied:
            logger.error("Access denied when trying to kill process  │  pid=%d", pid)
            return False
            
        except Exception as exc:
            logger.error("Failed to kill process %d: %s", pid, exc)
            return False
