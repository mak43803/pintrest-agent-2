"""
Cron Manager — Parses and calculates recurring schedule intervals.
===================================================================

Provides math for "Daily", "Weekly", and generic "Interval" scheduling.
Calculates the exact UNIX timestamp for the *next* execution based on
the current time and the schedule rule.

Usage::

    from scheduler.cron_manager import CronManager
    
    next_run = CronManager.next_daily("14:30")
    next_run_weekly = CronManager.next_weekly("Monday", "09:00")
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger("pinterest_agent.scheduler.cron")


class CronManager:
    """Calculates upcoming execution timestamps for scheduled tasks."""

    DAYS_OF_WEEK = {
        "monday": 0, "tuesday": 1, "wednesday": 2, 
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
    }

    @staticmethod
    def next_interval(seconds: int) -> float:
        """
        Calculate the timestamp for exactly `seconds` from now.
        """
        return time.time() + seconds

    @staticmethod
    def next_daily(time_str: str) -> float:
        """
        Calculate the next timestamp for a daily execution.
        
        Args:
            time_str: A string in "HH:MM" 24-hour format.
            
        Returns:
            UNIX timestamp of the next occurrence.
        """
        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError as e:
            raise ValueError(f"Invalid time format '{time_str}'. Expected 'HH:MM'") from e

        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If the target time has already passed today, schedule for tomorrow
        if target <= now:
            target += timedelta(days=1)

        return target.timestamp()

    @staticmethod
    def next_weekly(day_of_week: str, time_str: str) -> float:
        """
        Calculate the next timestamp for a weekly execution.
        
        Args:
            day_of_week: E.g., "Monday", "Tuesday".
            time_str: A string in "HH:MM" format.
            
        Returns:
            UNIX timestamp of the next occurrence.
        """
        day_lower = day_of_week.lower()
        if day_lower not in CronManager.DAYS_OF_WEEK:
            raise ValueError(f"Invalid day of week: {day_of_week}")
            
        target_weekday = CronManager.DAYS_OF_WEEK[day_lower]
        
        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError as e:
            raise ValueError(f"Invalid time format '{time_str}'. Expected 'HH:MM'") from e

        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Calculate days ahead
        days_ahead = target_weekday - now.weekday()
        
        # If it's today, but the time has passed, or if the day is in the past week
        if days_ahead < 0 or (days_ahead == 0 and target <= now):
            days_ahead += 7
            
        target += timedelta(days=days_ahead)

        return target.timestamp()
