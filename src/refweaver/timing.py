"""Timing and profiling utilities for RefWeaver."""

import functools
import time
from typing import Any, Callable

from loguru import logger


def timed(func: Callable) -> Callable:
    """Decorator to log execution time of a function.

    Usage:
        @timed
        def my_slow_function():
            ...

    Logs:
        DEBUG: Function name and execution time in ms
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            logger.debug(f"⏱ {func.__qualname__} took {elapsed:.1f}ms")
    return wrapper


def timed_info(func: Callable) -> Callable:
    """Decorator to log execution time at INFO level.

    Use this for high-level operations you always want to see timing for.

    Usage:
        @timed_info
        def search_articles():
            ...

    Logs:
        INFO: Function name and execution time
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            logger.info(f"⏱ {func.__qualname__} took {elapsed:.2f}s")
    return wrapper


class Timer:
    """Context manager for timing code blocks.

    Usage:
        with Timer("semantic_search"):
            results = adapter.search(query)

    Logs:
        DEBUG: Block name and execution time
    """

    def __init__(self, name: str, level: str = "debug") -> None:
        self.name = name
        self.level = level
        self.start: float = 0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        elapsed = (time.perf_counter() - self.start) * 1000
        msg = f"⏱ {self.name} took {elapsed:.1f}ms"
        if self.level == "info":
            logger.info(msg)
        else:
            logger.debug(msg)

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return (time.perf_counter() - self.start) * 1000

    @property
    def elapsed_s(self) -> float:
        """Get elapsed time in seconds."""
        return time.perf_counter() - self.start
