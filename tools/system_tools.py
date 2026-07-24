"""
System Tools — OS and Hardware monitoring.
============================================

Provides visibility into the host machine's CPU, RAM, Disk usage,
and general OS information.

Requires the ``psutil`` package.

Usage::

    from tools.system_tools import SystemTools
    
    cpu = SystemTools.get_cpu_usage()
    print(f"CPU Usage: {cpu}%")
"""

from __future__ import annotations

import logging
import platform
import shutil
from dataclasses import dataclass

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger("pinterest_agent.tools.system")


@dataclass
class SystemInfo:
    """Snapshot of current system state."""
    os_name: str
    os_release: str
    architecture: str
    cpu_percent: float
    ram_percent: float
    ram_total_gb: float
    disk_percent: float
    disk_total_gb: float


class SystemTools:
    """Operations for querying system and hardware metrics."""

    @staticmethod
    def get_cpu_usage() -> float:
        """Return the current CPU usage percentage."""
        if HAS_PSUTIL:
            # interval=0.1 prevents blocking for a full second
            return psutil.cpu_percent(interval=0.1)
        logger.warning("psutil not installed. CPU usage unavailable.")
        return 0.0

    @staticmethod
    def get_ram_usage() -> dict[str, float]:
        """
        Return RAM metrics in GB and percentage.
        Returns:
            Dict containing 'total_gb', 'used_gb', and 'percent'.
        """
        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "percent": mem.percent
            }
        logger.warning("psutil not installed. RAM usage unavailable.")
        return {"total_gb": 0.0, "used_gb": 0.0, "percent": 0.0}

    @staticmethod
    def get_disk_usage(path: str = "/") -> dict[str, float]:
        """
        Return Disk metrics in GB and percentage.
        Args:
            path: The mount point or path to check (default: root).
        Returns:
            Dict containing 'total_gb', 'used_gb', and 'percent'.
        """
        try:
            # We can use standard library shutil for disk usage
            usage = shutil.disk_usage(path)
            total = usage.total
            used = usage.used
            percent = (used / total) * 100 if total > 0 else 0.0
            
            return {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "percent": round(percent, 1)
            }
        except Exception as exc:
            logger.error("Failed to read disk usage: %s", exc)
            return {"total_gb": 0.0, "used_gb": 0.0, "percent": 0.0}

    @staticmethod
    def get_os_info() -> dict[str, str]:
        """Return basic operating system details."""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

    @staticmethod
    def get_full_snapshot() -> SystemInfo:
        """Collect all system metrics into a single snapshot."""
        os_info = SystemTools.get_os_info()
        ram = SystemTools.get_ram_usage()
        
        # Determine the primary disk drive based on OS
        drive = "C:\\\\" if os_info["system"] == "Windows" else "/"
        disk = SystemTools.get_disk_usage(drive)
        
        return SystemInfo(
            os_name=os_info["system"],
            os_release=os_info["release"],
            architecture=os_info["machine"],
            cpu_percent=SystemTools.get_cpu_usage(),
            ram_percent=ram["percent"],
            ram_total_gb=ram["total_gb"],
            disk_percent=disk["percent"],
            disk_total_gb=disk["total_gb"],
        )
