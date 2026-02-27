"""Shared FastAPI dependencies."""

import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, Header

from refweaver.api.errors import http_error
from refweaver.api.settings import SETTINGS


def get_user_id(
    user_id: str | None = Header(default=None, alias=SETTINGS.api_user_header),
) -> str:
    if not user_id:
        raise http_error("missing_user", "Missing user id header", status_code=400)
    return user_id


def verify_api_key(
    api_key: str | None = Header(default=None, alias=SETTINGS.api_key_header),
) -> None:
    if SETTINGS.api_key is None:
        return
    if api_key != SETTINGS.api_key:
        raise http_error("unauthorized", "Invalid API key", status_code=401)


_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def rate_limit_user(user_id: str = Depends(get_user_id)) -> None:
    """Enforce a simple per-user request limit per minute."""
    limit = SETTINGS.rate_limit_per_minute
    if limit <= 0:
        return

    now = time.monotonic()
    cutoff = now - 60.0
    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS[user_id]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            raise http_error(
                "rate_limited",
                "Rate limit exceeded",
                status_code=429,
                details={"limit_per_minute": str(limit)},
            )
        bucket.append(now)
