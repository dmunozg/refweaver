"""Retry utilities with exponential backoff."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

from loguru import logger

T = TypeVar("T")


def retry_call(
    func: Callable[..., T],
    *args: object,
    retries: int = 2,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    jitter: float = 0.1,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    **kwargs: object,
) -> T:
    """Call a function with exponential backoff retries.

    Args:
        func: Callable to execute.
        *args: Positional arguments passed to func.
        retries: Number of retries after the initial attempt.
        base_delay: Initial backoff delay in seconds.
        max_delay: Maximum delay between retries in seconds.
        jitter: Fractional jitter applied to delay (0.1 = +/-10%).
        exceptions: Exception types that trigger a retry.
        **kwargs: Keyword arguments passed to func.

    Returns:
        The result of func(*args, **kwargs).

    Raises:
        The last caught exception after retries are exhausted.
    """
    attempt = 0
    while True:
        try:
            return func(*args, **kwargs)
        except exceptions as exc:
            attempt += 1
            if attempt > retries:
                raise

            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            if jitter > 0:
                jitter_factor = 1 + random.uniform(-jitter, jitter)
                delay = max(0.0, delay * jitter_factor)

            logger.warning(
                f"Retrying {func.__qualname__} after error: {exc!r} "
                f"(attempt {attempt}/{retries}, delay {delay:.2f}s)"
            )
            time.sleep(delay)
