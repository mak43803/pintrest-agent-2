"""
Scheduler — Orchestrator for recurring and delayed tasks.
==========================================================

The Scheduler manages the execution of tasks that need to run at a
specific time, after a delay, or on a recurring basis. It persists
state to SQLite to survive crashes and integrates with the main
Agent Planner for actual execution.

Features:
    • Persistent SQLite checkpointing (scheduled_tasks table)
    • Async execution loop with interruptible sleep
    • Graceful pause, resume, and cancel functionality
    • Auto-rescheduling for recurring tasks
    
Usage::

    from scheduler.scheduler import Scheduler
    from database.database import Database
    
    db = Database(...)
    scheduler = Scheduler(db, agent_callback=my_agent_func)
    
    # Schedule a task to run in 5 minutes
    await scheduler.schedule_in(300, "pin_product", payload={"product_id": 4})
    
    # Run the background loop
    await scheduler.start()
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable, Coroutine

from database.database import Database
from scheduler.cron_manager import CronManager
from scheduler.task_queue import ScheduledTask, TaskQueue
from scheduler.timer import InterruptibleTimer

logger = logging.getLogger("pinterest_agent.scheduler")


# Callback type for when a task fires
AgentCallback = Callable[[ScheduledTask], Coroutine[Any, Any, None]]


class Scheduler:
    """
    Central scheduler for the Pinterest AI Agent.
    
    Args:
        db:             Initialized SQLite Database instance.
        agent_callback: Async function to call when a task is ready to execute.
    """

    def __init__(self, db: Database, agent_callback: AgentCallback) -> None:
        self._db = db
        self._callback = agent_callback
        
        self._queue = TaskQueue()
        self._timer = InterruptibleTimer()
        
        self._is_running = False
        self._is_paused = False
        self._main_task: asyncio.Task[None] | None = None
        
        self._init_schema()
        logger.info("Scheduler initialized.")

    def _init_schema(self) -> None:
        """Create the scheduled_tasks table if it doesn't exist."""
        sql = """
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id           TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                run_at       REAL NOT NULL,
                priority     INTEGER NOT NULL,
                func_name    TEXT NOT NULL,
                payload      TEXT NOT NULL, -- JSON
                is_recurring BOOLEAN NOT NULL,
                cron_expr    TEXT,
                interval_sec INTEGER,
                status       TEXT NOT NULL,
                retries      INTEGER NOT NULL
            )
        """
        self._db.execute(sql)
        logger.debug("Scheduler schema verified.")

    # ── Scheduling API ─────────────────────────────────────────────────

    async def schedule_in(
        self,
        seconds: int,
        name: str,
        priority: int = 1,
        func_name: str = "",
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Schedule a one-off task to run after a delay."""
        run_at = CronManager.next_interval(seconds)
        return await self._add_task(
            name=name, run_at=run_at, priority=priority,
            func_name=func_name, payload=payload
        )

    async def schedule_daily(
        self,
        time_str: str,
        name: str,
        priority: int = 5,
        func_name: str = "",
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Schedule a recurring daily task."""
        run_at = CronManager.next_daily(time_str)
        return await self._add_task(
            name=name, run_at=run_at, priority=priority,
            func_name=func_name, payload=payload,
            is_recurring=True, cron_expr=f"daily {time_str}"
        )

    async def schedule_interval(
        self,
        seconds: int,
        name: str,
        priority: int = 5,
        func_name: str = "",
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Schedule a task that repeats every X seconds."""
        run_at = CronManager.next_interval(seconds)
        return await self._add_task(
            name=name, run_at=run_at, priority=priority,
            func_name=func_name, payload=payload,
            is_recurring=True, interval_sec=seconds
        )

    async def _add_task(self, **kwargs: Any) -> str:
        """Internal method to build, save, and enqueue a task."""
        task_id = str(uuid.uuid4())
        task = ScheduledTask(id=task_id, **kwargs)
        
        # Save to DB for checkpoints
        self._save_checkpoint(task)
        
        # Add to runtime queue
        await self._queue.push(task)
        
        # Wake up the timer if this new task should run earlier than the current sleep
        if self._timer.is_sleeping and self._timer.target_time:
            if task.run_at < self._timer.target_time:
                self._timer.wake()
                
        logger.info(
            "Task scheduled  │  id=%s  name=%s  run_at=%.1f",
            task_id, task.name, task.run_at
        )
        return task_id

    # ── State Management ───────────────────────────────────────────────

    def pause(self) -> None:
        """Pause execution. Tasks will queue but not fire."""
        self._is_paused = True
        logger.info("Scheduler paused.")

    def resume(self) -> None:
        """Resume execution."""
        self._is_paused = False
        self._timer.wake()
        logger.info("Scheduler resumed.")

    async def cancel(self, task_id: str) -> bool:
        """Cancel a specific task by ID."""
        success = await self._queue.remove(task_id)
        if success:
            sql = "UPDATE scheduled_tasks SET status = 'cancelled' WHERE id = ?"
            self._db.execute(sql, (task_id,))
            logger.info("Task cancelled successfully  │  id=%s", task_id)
        return success

    # ── Persistence (Checkpoints) ──────────────────────────────────────

    def _save_checkpoint(self, task: ScheduledTask) -> None:
        """Persist task to SQLite."""
        sql = """
            INSERT OR REPLACE INTO scheduled_tasks
            (id, name, run_at, priority, func_name, payload, is_recurring, cron_expr, interval_sec, status, retries)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        payload_str = json.dumps(task.payload) if task.payload else "{}"
        self._db.execute(
            sql,
            (
                task.id, task.name, task.run_at, task.priority, task.func_name,
                payload_str, task.is_recurring, task.cron_expr, task.interval_sec,
                task.status, task.retries
            )
        )

    def _remove_checkpoint(self, task_id: str) -> None:
        """Remove task from SQLite."""
        self._db.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))

    async def load_checkpoints(self) -> None:
        """
        Load pending tasks from SQLite on startup.
        Should be called before start().
        """
        await self._queue.clear()
        
        sql = "SELECT * FROM scheduled_tasks WHERE status = 'queued'"
        rows = self._db.fetchall(sql)
        
        for row in rows:
            task = ScheduledTask(
                id=row["id"],
                name=row["name"],
                run_at=row["run_at"],
                priority=row["priority"],
                func_name=row["func_name"],
                payload=json.loads(row["payload"]),
                is_recurring=bool(row["is_recurring"]),
                cron_expr=row["cron_expr"],
                interval_sec=row["interval_sec"],
                status=row["status"],
                retries=row["retries"],
            )
            await self._queue.push(task)
            
        logger.info("Loaded %d scheduled tasks from checkpoint.", len(rows))

    # ── Main Loop ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background execution loop."""
        if self._is_running:
            return
            
        self._is_running = True
        self._main_task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started.")

    async def stop(self) -> None:
        """Stop the background loop."""
        self._is_running = False
        self._timer.wake()
        
        if self._main_task:
            try:
                await asyncio.wait_for(self._main_task, timeout=2.0)
            except asyncio.TimeoutError:
                self._main_task.cancel()
        logger.info("Scheduler stopped.")

    async def _run_loop(self) -> None:
        """The core execution loop."""
        while self._is_running:
            if self._is_paused:
                # If paused, wait a bit and check again
                await asyncio.sleep(1.0)
                continue
                
            task = await self._queue.peek()
            
            if not task:
                # Queue empty, wait for a new task to be pushed (which triggers wake)
                # We sleep for a long time, assuming wake() will interrupt us
                await self._timer.sleep_until(time.time() + 86400)
                continue
                
            if task.status == "cancelled":
                # Clean up cancelled tasks
                await self._queue.pop()
                self._remove_checkpoint(task.id)
                continue

            now = time.time()
            if task.run_at <= now:
                # Time to execute!
                popped_task = await self._queue.pop()
                asyncio.create_task(self._execute_task(popped_task))
            else:
                # Not ready yet, sleep until its scheduled time
                await self._timer.sleep_until(task.run_at)

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Fire the callback and handle recurring logic."""
        logger.info("Executing scheduled task  │  id=%s  name=%s", task.id, task.name)
        
        try:
            # Pass execution to the Agent Core
            await self._callback(task)
            
            if task.is_recurring:
                # Calculate next run time and re-queue
                await self._reschedule_recurring(task)
            else:
                # One-off task complete, remove checkpoint
                self._remove_checkpoint(task.id)
                
        except Exception as exc:
            logger.error("Error executing task %s: %s", task.id, exc, exc_info=True)
            # Basic retry logic could be added here
            if task.retries < 3:
                task.retries += 1
                task.run_at = time.time() + 60 * task.retries  # Exponential backoff (basic)
                self._save_checkpoint(task)
                await self._queue.push(task)
                logger.info("Task requeued for retry  │  id=%s  attempt=%d", task.id, task.retries)
            else:
                logger.error("Task max retries reached. Dropping  │  id=%s", task.id)
                self._remove_checkpoint(task.id)

    async def _reschedule_recurring(self, task: ScheduledTask) -> None:
        """Calculate the next interval and re-queue a recurring task."""
        try:
            if task.interval_sec:
                task.run_at = CronManager.next_interval(task.interval_sec)
            elif task.cron_expr and task.cron_expr.startswith("daily "):
                time_str = task.cron_expr.split(" ")[1]
                task.run_at = CronManager.next_daily(time_str)
            else:
                logger.warning("Unknown recurring format for task %s", task.id)
                self._remove_checkpoint(task.id)
                return

            task.retries = 0
            self._save_checkpoint(task)
            await self._queue.push(task)
            
            logger.debug("Recurring task rescheduled  │  id=%s  next_run=%.1f", task.id, task.run_at)
        except Exception as exc:
            logger.error("Failed to reschedule task %s: %s", task.id, exc)
            self._remove_checkpoint(task.id)
