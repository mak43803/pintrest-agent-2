"""
Checkpoint — Data structures and serialization for workflow recovery.
======================================================================

Defines the exact state needed to resume an interrupted workflow.
Integrates directly with the SQLite database to fetch tasks that were
abruptly halted (e.g., power failure) while in the 'Running' state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from database.database import Database
from database.models import Status


@dataclass
class CheckpointData:
    """Represents a frozen snapshot of an interrupted task."""
    task_id: int
    task_name: str
    last_completed_step: str
    status: str
    retries: int
    started_at: str
    last_error: str | None


class Checkpoint:
    """
    Handles reading and writing workflow checkpoints to the database.
    
    Args:
        db: Initialized SQLite Database connection.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def get_interrupted_checkpoints(self) -> list[CheckpointData]:
        """
        Find all tasks that were left in the 'Running' state.
        
        This happens when the app crashes, loses power, or is forcefully
        rebooted while a workflow is executing.
        """
        sql = "SELECT * FROM tasks WHERE status = ? ORDER BY id ASC"
        rows = self._db.fetchall(sql, (Status.RUNNING.value,))
        
        checkpoints: list[CheckpointData] = []
        for row in rows:
            checkpoints.append(
                CheckpointData(
                    task_id=row["id"],
                    task_name=row["task_name"],
                    last_completed_step=row["current_step"],
                    status=row["status"],
                    retries=0, # Typically tracked on the product or scheduler, but tracked here conceptually
                    started_at=row["started_at"],
                    last_error=row["last_error"],
                )
            )
        return checkpoints

    def mark_checkpoint_failed(self, task_id: int, error: str) -> None:
        """Mark a recovered task as permanently failed if it cannot be resumed."""
        sql = "UPDATE tasks SET status = ?, last_error = ? WHERE id = ?"
        self._db.execute(sql, (Status.FAILED.value, error, task_id))

    def reset_checkpoint_to_pending(self, task_id: int) -> None:
        """Move an interrupted task back to Pending so the Planner can pick it up."""
        sql = "UPDATE tasks SET status = ?, last_error = NULL WHERE id = ?"
        self._db.execute(sql, (Status.PENDING.value, task_id))
