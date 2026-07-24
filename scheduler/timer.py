"""
Timer — Precision async timing for the Scheduler.
==================================================

Provides an interruptible async sleep mechanism. Used by the Scheduler
loop to sleep until the next task is ready, but allows immediate
wake-up if a new, higher-priority task is scheduled earlier.
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger("pinterest_agent.scheduler.timer")


class InterruptibleTimer:
    """
    An async timer that can be cancelled or woken up early.
    """

    def __init__(self) -> None:
        self._wake_event = asyncio.Event()
        self._target_time: float | None = None
        self._task: asyncio.Task[None] | None = None

    async def sleep_until(self, target_timestamp: float) -> bool:
        """
        Sleep until a specific unix timestamp.
        
        Args:
            target_timestamp: The time.time() float to sleep until.
            
        Returns:
            True if the timer finished naturally, False if it was interrupted.
        """
        self._wake_event.clear()
        self._target_time = target_timestamp
        
        now = time.time()
        delay = target_timestamp - now
        
        if delay <= 0:
            return True

        logger.debug("Timer sleeping for %.2fs", delay)
        
        try:
            # We use wait_for to sleep, but attach it to our wake event.
            # If the event is set early, wait_for completes immediately.
            # If the timeout hits, it raises TimeoutError which means we slept fully.
            await asyncio.wait_for(self._wake_event.wait(), timeout=delay)
            # If we reach here, we were woken up early.
            return False
            
        except asyncio.TimeoutError:
            # Sleep completed naturally
            return True
            
        except asyncio.CancelledError:
            # The whole scheduler loop is shutting down
            logger.debug("Timer cancelled.")
            raise
            
        finally:
            self._target_time = None

    def wake(self) -> None:
        """Wake up the timer immediately."""
        if not self._wake_event.is_set():
            logger.debug("Timer interrupted (woken early).")
            self._wake_event.set()

    @property
    def is_sleeping(self) -> bool:
        """Return True if currently sleeping."""
        return self._target_time is not None
        
    @property
    def target_time(self) -> float | None:
        """Return the target timestamp being waited for, or None."""
        return self._target_time
