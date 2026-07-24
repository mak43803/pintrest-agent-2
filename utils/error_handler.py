"""
Error Handler — Global exception trapping and performance logging.
===================================================================

Hooks into sys.excepthook to capture unhandled exceptions securely
before the app crashes. Also provides decorators for execution
logging and performance profiling (timing).

Usage::

    from logs.error_handler import setup_global_exception_handler, log_execution
    
    setup_global_exception_handler(log_manager)
    
    @log_execution(module="database")
    def my_risky_function():
        pass
"""

from __future__ import annotations

import functools
import logging
import sys
import time
import traceback
from typing import Any, Callable

from utils.log_manager import LogManager

logger = logging.getLogger("pinterest_agent.logs.error")


def setup_global_exception_handler(log_manager: LogManager) -> None:
    """
    Hook into Python's sys.excepthook to capture fatal unhandled exceptions.
    
    Args:
        log_manager: Initialized LogManager to save the crash into SQLite.
    """
    def _handle_exception(exc_type: type, exc_value: BaseException, exc_traceback: Any) -> None:
        # Ignore KeyboardInterrupt (Ctrl+C)
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # Format the traceback
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_text = "".join(tb_lines)

        # Log via standard logging
        logger.critical("Uncaught Exception: %s\\n%s", exc_value, tb_text)

        # Save to SQLite
        log_manager.save_log(
            level="CRITICAL",
            message=f"Uncaught {exc_type.__name__}: {exc_value}",
            module="system.crash",
        )

        # Call the original excepthook to let Python crash normally
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _handle_exception
    logger.debug("Global exception handler installed.")


def log_execution(module: str = "general") -> Callable[..., Any]:
    """
    Decorator that logs function execution time and traps exceptions.

    Args:
        module: The component name to log under (e.g. "llm", "browser").

    Returns:
        The wrapped function.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = func.__name__
            start_time = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as exc:
                logger.error(
                    "Execution failed  │  module=%s  func=%s  error=%s",
                    module, func_name, exc
                )
                raise
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(
                    "Execution metrics  │  module=%s  func=%s  time=%.2fms",
                    module, func_name, duration_ms
                )
                
        # We also need an async wrapper to support async functions properly
        import asyncio
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                func_name = func.__name__
                start_time = time.perf_counter()
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as exc:
                    logger.error(
                        "Async execution failed  │  module=%s  func=%s  error=%s",
                        module, func_name, exc
                    )
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    logger.debug(
                        "Async metrics  │  module=%s  func=%s  time=%.2fms",
                        module, func_name, duration_ms
                    )
            return async_wrapper
            
        return sync_wrapper
    return decorator
