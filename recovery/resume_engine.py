"""
Resume Engine — Decision logic for recovering tasks post-crash.
================================================================

Validates network connectivity and decides whether a broken checkpoint
should be retried, reset, or permanently failed based on retry limits.

Features:
    • Ping/Internet connection verification
    • Retry counting and limits
    • Graceful restoration of interrupted tasks
"""

from __future__ import annotations

import logging
import socket
from typing import Any

from recovery.checkpoint import Checkpoint, CheckpointData

logger = logging.getLogger("pinterest_agent.recovery.engine")


class ResumeEngine:
    """
    Evaluates checkpoints and orchestrates their recovery.
    
    Args:
        checkpoint_store: Initialized Checkpoint instance.
        max_retries:      Maximum number of times a task can be retried.
    """

    def __init__(self, checkpoint_store: Checkpoint, max_retries: int = 3) -> None:
        self._store = checkpoint_store
        self._max_retries = max_retries
        logger.info("ResumeEngine initialized  │  max_retries=%d", max_retries)

    @staticmethod
    def is_internet_available(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
        """
        Check for active internet connection (crucial for Pinterest actions).
        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except socket.error:
            return False

    def process_checkpoint(self, checkpoint: CheckpointData) -> bool:
        """
        Evaluate a single interrupted task and attempt recovery.
        
        Args:
            checkpoint: The snapshot of the interrupted task.
            
        Returns:
            True if successfully recovered (queued for resume), False if failed.
        """
        logger.info(
            "Evaluating checkpoint  │  task_id=%d  step='%s'",
            checkpoint.task_id,
            checkpoint.last_completed_step,
        )

        # 1. Check Network Connectivity
        if not self.is_internet_available():
            logger.warning("Internet unavailable. Cannot recover task %d right now.", checkpoint.task_id)
            return False

        # 2. Check Retry Limits
        if checkpoint.retries >= self._max_retries:
            logger.error("Task %d exceeded max retries. Marking as Failed.", checkpoint.task_id)
            self._store.mark_checkpoint_failed(
                checkpoint.task_id, 
                error=f"Max retries ({self._max_retries}) exceeded during crash recovery."
            )
            return False

        # 3. Restore to Pending
        # By setting the status to PENDING, the main Planner loop will automatically
        # pick this up on its next cycle and call planner.resume() internally
        # since it still has its `current_step` saved in the DB.
        self._store.reset_checkpoint_to_pending(checkpoint.task_id)
        logger.info("Task %d successfully queued for resume.", checkpoint.task_id)
        
        return True
