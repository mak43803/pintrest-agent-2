"""
Recovery Module — Post-crash agent restoration and self-healing.
================================================================

Handles detecting interrupted tasks after a hard crash or power failure.
Evaluates network conditions, enforces retry limits, and automatically
restores broken tasks back into the Agent Planner's active queue.

Quick Start::

    from database import Database
    from recovery import RecoveryManager
    
    db = Database(...)
    recovery = RecoveryManager(db)
    
    # Run once during boot
    await recovery.execute_startup_recovery()

Public API:
    - RecoveryManager — The main orchestrator
    - Checkpoint      — SQLite state persistence
    - ResumeEngine    — Logic for when and how to resume
"""

from recovery.recovery_manager import RecoveryManager
from recovery.resume_engine import ResumeEngine
from recovery.checkpoint import Checkpoint, CheckpointData

__all__ = [
    "RecoveryManager",
    "ResumeEngine",
    "Checkpoint",
    "CheckpointData",
]
