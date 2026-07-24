"""
Task Manager — Task lifecycle management with database persistence.
====================================================================

Manages the full lifecycle of agent tasks: creation, starting,
pausing, resuming, cancelling, and completion. Every state change
is persisted to the SQLite ``tasks`` table via the ``Repository``.

The Task Manager operates as a layer between the Planner (which
decides *what* to do) and the Database (which stores *state*).

Public API:

    create_task(name)       → int           Create a new task, return its id.
    start_task(id)          → None          Mark task as Running.
    pause_task(id)          → None          Mark task as Waiting.
    resume_task(id)         → None          Resume a paused task.
    cancel_task(id)         → None          Mark task as Skipped.
    complete_task(id)       → None          Mark task as Completed.
    fail_task(id, error)    → None          Mark task as Failed with error.
    retry_task(id)          → None          Reset task for retry.
    get_task(id)            → Task | None   Fetch a task by id.
    get_pending_tasks()     → list[Task]    Fetch all pending tasks.
    get_active_task()       → Task | None   Fetch the currently running task.
    update_step(id, step)   → None          Update the current step name.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from database.database import Database
from database.models import Status, Task

logger = logging.getLogger("pinterest_agent.planner.task_manager")


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TaskManager:
    """
    Task lifecycle manager with SQLite persistence.

    All task state transitions are written to the ``tasks`` table
    immediately. The manager uses parameterized queries and
    transactional writes via the ``Database`` connection manager.

    Args:
        db: An initialized ``Database`` instance (Dependency Injection).
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(self, db: Database) -> None:
        self._db = db
        logger.info("TaskManager initialized.")

    # ═══════════════════════════════════════════════════════════════════
    #  CREATE
    # ═══════════════════════════════════════════════════════════════════

    def create_task(self, task_name: str) -> int:
        """
        Create a new task with status ``Pending``.

        Args:
            task_name: A human-readable task identifier.

        Returns:
            The auto-generated task ``id``.

        Raises:
            DatabaseQueryError: If the insert fails.
        """
        sql = """
            INSERT INTO tasks (task_name, current_step, status)
            VALUES (?, '', ?)
        """
        cursor = self._db.execute(sql, (task_name, Status.PENDING.value))
        task_id = cursor.lastrowid

        logger.info(
            "Task created  │  id=%d  name=%s  status=%s",
            task_id,
            task_name,
            Status.PENDING.value,
        )
        return task_id

    # ═══════════════════════════════════════════════════════════════════
    #  LIFECYCLE TRANSITIONS
    # ═══════════════════════════════════════════════════════════════════

    def start_task(self, task_id: int) -> None:
        """
        Transition a task from Pending → Running.

        Args:
            task_id: The task's primary key.

        Raises:
            DatabaseQueryError: If the update fails.
        """
        sql = """
            UPDATE tasks
               SET status = ?, started_at = ?, last_error = NULL
             WHERE id = ?
        """
        self._db.execute(sql, (Status.RUNNING.value, _utc_now(), task_id))
        logger.info("Task started  │  id=%d  status=Running", task_id)

    def pause_task(self, task_id: int) -> None:
        """
        Pause a running task (Running → Waiting).

        The task retains its ``current_step`` so it can be resumed.

        Args:
            task_id: The task's primary key.
        """
        sql = "UPDATE tasks SET status = ? WHERE id = ?"
        self._db.execute(sql, (Status.PENDING.value, task_id))
        logger.info("Task paused  │  id=%d  status=Pending (paused)", task_id)

    def resume_task(self, task_id: int) -> None:
        """
        Resume a paused task (Pending/Waiting → Running).

        Args:
            task_id: The task's primary key.
        """
        sql = "UPDATE tasks SET status = ? WHERE id = ?"
        self._db.execute(sql, (Status.RUNNING.value, task_id))
        logger.info("Task resumed  │  id=%d  status=Running", task_id)

    def cancel_task(self, task_id: int) -> None:
        """
        Cancel a task (any state → Skipped).

        Args:
            task_id: The task's primary key.
        """
        sql = "UPDATE tasks SET status = ?, finished_at = ? WHERE id = ?"
        self._db.execute(sql, (Status.SKIPPED.value, _utc_now(), task_id))
        logger.info("Task cancelled  │  id=%d  status=Skipped", task_id)

    def complete_task(self, task_id: int) -> None:
        """
        Mark a task as successfully completed (Running → Completed).

        Args:
            task_id: The task's primary key.
        """
        sql = """
            UPDATE tasks
               SET status = ?, finished_at = ?
             WHERE id = ?
        """
        self._db.execute(sql, (Status.COMPLETED.value, _utc_now(), task_id))
        logger.info("Task completed  │  id=%d  status=Completed", task_id)

    def fail_task(self, task_id: int, error: str) -> None:
        """
        Mark a task as failed with an error message.

        Args:
            task_id: The task's primary key.
            error:   Description of the failure.
        """
        sql = """
            UPDATE tasks
               SET status = ?, finished_at = ?, last_error = ?
             WHERE id = ?
        """
        self._db.execute(
            sql, (Status.FAILED.value, _utc_now(), error, task_id)
        )
        logger.error("Task failed  │  id=%d  error=%s", task_id, error[:100])

    def retry_task(self, task_id: int) -> None:
        """
        Reset a failed task for retry (Failed → Pending).

        Clears the error message and finished timestamp.

        Args:
            task_id: The task's primary key.
        """
        sql = """
            UPDATE tasks
               SET status = ?, finished_at = NULL, last_error = NULL
             WHERE id = ?
        """
        self._db.execute(sql, (Status.PENDING.value, task_id))
        logger.info("Task reset for retry  │  id=%d  status=Pending", task_id)

    # ═══════════════════════════════════════════════════════════════════
    #  STEP TRACKING
    # ═══════════════════════════════════════════════════════════════════

    def update_step(self, task_id: int, step_name: str) -> None:
        """
        Update the current step of a running task.

        Used for checkpoint/resume: if the agent crashes, it can
        read ``current_step`` and resume from that point.

        Args:
            task_id:   The task's primary key.
            step_name: Name of the step currently being executed.
        """
        sql = "UPDATE tasks SET current_step = ? WHERE id = ?"
        self._db.execute(sql, (step_name, task_id))
        logger.debug("Task step updated  │  id=%d  step=%s", task_id, step_name)

    # ═══════════════════════════════════════════════════════════════════
    #  QUERIES
    # ═══════════════════════════════════════════════════════════════════

    def get_task(self, task_id: int) -> Optional[Task]:
        """
        Fetch a task by its primary key.

        Args:
            task_id: The task's primary key.

        Returns:
            A ``Task`` instance, or ``None`` if not found.
        """
        sql = "SELECT * FROM tasks WHERE id = ?"
        row = self._db.fetchone(sql, (task_id,))
        return Task.from_row(row) if row else None

    def get_pending_tasks(self) -> list[Task]:
        """
        Fetch all tasks with status ``Pending``, ordered by id (FIFO).

        Returns:
            A list of pending ``Task`` instances.
        """
        sql = "SELECT * FROM tasks WHERE status = ? ORDER BY id ASC"
        rows = self._db.fetchall(sql, (Status.PENDING.value,))
        tasks = [Task.from_row(r) for r in rows]
        logger.debug("Pending tasks retrieved  │  count=%d", len(tasks))
        return tasks

    def get_active_task(self) -> Optional[Task]:
        """
        Fetch the currently running task (if any).

        Returns:
            The active ``Task``, or ``None`` if nothing is running.
        """
        sql = "SELECT * FROM tasks WHERE status = ? LIMIT 1"
        row = self._db.fetchone(sql, (Status.RUNNING.value,))
        return Task.from_row(row) if row else None

    def get_failed_tasks(self) -> list[Task]:
        """
        Fetch all failed tasks, ordered by most recent first.

        Returns:
            A list of failed ``Task`` instances.
        """
        sql = "SELECT * FROM tasks WHERE status = ? ORDER BY id DESC"
        rows = self._db.fetchall(sql, (Status.FAILED.value,))
        return [Task.from_row(r) for r in rows]

    def get_all_tasks(self) -> list[Task]:
        """
        Fetch all tasks, ordered by id descending (newest first).

        Returns:
            A list of all ``Task`` instances.
        """
        sql = "SELECT * FROM tasks ORDER BY id DESC"
        rows = self._db.fetchall(sql)
        return [Task.from_row(r) for r in rows]

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return "TaskManager(db=...)"
