"""
Recovery Manager — Orchestrator for post-crash recovery operations.
=====================================================================

Designed to be run exactly once when the Agent Core boots up.
It coordinates the Checkpoint and ResumeEngine modules to scan the SQLite
database for broken sessions and safely enqueue them for execution.

Features:
    • Single entry point for startup recovery
    • Thread-safe orchestration
    • Integration with the Logs module for audit trails
"""

from __future__ import annotations

import asyncio
import logging

from database.database import Database
from recovery.checkpoint import Checkpoint
from recovery.resume_engine import ResumeEngine

logger = logging.getLogger("pinterest_agent.recovery")


class RecoveryManager:
    """
    Top-level recovery orchestrator.
    
    Args:
        db:          Initialized SQLite Database connection.
        max_retries: Limit for failed task restarts.
    """

    def __init__(self, db: Database, max_retries: int = 3) -> None:
        self._db = db
        self._checkpoint_store = Checkpoint(db)
        self._resume_engine = ResumeEngine(self._checkpoint_store, max_retries)
        self._lock = asyncio.Lock()
        
        logger.info("RecoveryManager initialized.")

    async def execute_startup_recovery(self) -> int:
        """
        Scan for and recover interrupted tasks on boot.
        
        Returns:
            The number of tasks successfully queued for recovery.
        """
        async with self._lock:
            logger.info("Initiating startup recovery scan...")
            
            checkpoints = self._checkpoint_store.get_interrupted_checkpoints()
            if not checkpoints:
                logger.info("No interrupted tasks found. System state is clean.")
                return 0
                
            logger.warning("Found %d interrupted task(s) from previous session.", len(checkpoints))
            
            recovered_count = 0
            for cp in checkpoints:
                success = self._resume_engine.process_checkpoint(cp)
                if success:
                    recovered_count += 1
                    
            logger.info("Startup recovery complete  │  recovered=%d/%d", recovered_count, len(checkpoints))
            return recovered_count
