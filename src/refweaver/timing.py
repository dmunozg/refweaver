"""Timing and profiling utilities for RefWeaver."""

import functools
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")


def timed[T](func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to log execution time of a function.

    Usage:
        @timed
        def my_slow_function():
            ...

    Logs:
        DEBUG: Function name and execution time in ms
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            logger.debug(f"⏱ {func.__qualname__} took {elapsed:.1f}ms")

    return wrapper


def timed_info[T](func: Callable[..., T]) -> Callable[..., T]:
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
    def wrapper(*args: Any, **kwargs: Any) -> T:
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


def run_with_timeout[T](
    func: Callable[..., T],
    timeout_seconds: float,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run a function with a timeout.

    Args:
        func: Function to run.
        timeout_seconds: Maximum time to wait.
        *args: Positional arguments for func.
        **kwargs: Keyword arguments for func.

    Returns:
        Result of func(*args, **kwargs).

    Raises:
        TimeoutError: If function takes longer than timeout_seconds.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(func, *args, **kwargs)
    timed_out = False
    try:
        return future.result(timeout=timeout_seconds)
    except TimeoutError as _err:
        timed_out = True
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError(
            f"Function {func.__qualname__} timed out after {timeout_seconds}s"
        ) from _err
    finally:
        if not timed_out:
            executor.shutdown(wait=True)


def timeout(seconds: float) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add timeout to a function.

    Usage:
        @timeout(15.0)
        def slow_function():
            ...

    Args:
        seconds: Timeout in seconds.

    Returns:
        Decorated function that raises TimeoutError if exceeded.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return run_with_timeout(func, seconds, *args, **kwargs)

        return wrapper

    return decorator
