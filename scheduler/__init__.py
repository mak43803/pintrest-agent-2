"""
Scheduler Module — Background task scheduling and execution.
============================================================

Provides the ability to delay tasks, run them on a recurring interval,
or schedule them for specific times (e.g. daily, weekly). Backed by
SQLite for crash resilience and designed to run asynchronously alongside
the main Agent Planner.

Quick Start::
    from scheduler import Scheduler
    from database import Database
    
    async def my_callback(task):
        print(f"Running: {task.name}")

    db = Database(...)
    sched = Scheduler(db, my_callback)
    await sched.load_checkpoints()
    await sched.start()

    # Schedule daily at 2:30 PM
    await sched.schedule_daily("14:30", "daily_pin")

Public API:
    - Scheduler       — The main background orchestrator
    - ScheduledTask   — Task dataclass
    - CronManager     — Interval math calculations
"""

from scheduler.scheduler import Scheduler, AgentCallback
from scheduler.task_queue import ScheduledTask, TaskQueue
from scheduler.cron_manager import CronManager
from scheduler.timer import InterruptibleTimer

__all__ = [
    "Scheduler",
    "AgentCallback",
    "ScheduledTask",
    "TaskQueue",
    "CronManager",
    "InterruptibleTimer",
]
