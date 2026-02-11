"""Simple per-service rate limiting utilities."""

from __future__ import annotations

import os
import threading
import time
from urllib.parse import urlparse


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = float(raw)
    except ValueError:
        return default

    return max(0.0, value)


def _default_intervals() -> dict[str, float]:
    return {
        "semantic_scholar": _env_float("REFWEAVER_RATE_LIMIT_SEMANTIC_SCHOLAR", 1.0),
        "openalex": _env_float("REFWEAVER_RATE_LIMIT_OPENALEX", 1.0),
        "google_scholar": _env_float("REFWEAVER_RATE_LIMIT_GOOGLE_SCHOLAR", 2.0),
        "perplexity": _env_float("REFWEAVER_RATE_LIMIT_PERPLEXITY", 2.0),
        "crossref": _env_float("REFWEAVER_RATE_LIMIT_CROSSREF", 1.0),
        "unpaywall": _env_float("REFWEAVER_RATE_LIMIT_UNPAYWALL", 1.0),
        "annas_archive": _env_float("REFWEAVER_RATE_LIMIT_ANNAS_ARCHIVE", 2.0),
        "doi": _env_float("REFWEAVER_RATE_LIMIT_DOI", 1.0),
        "publisher": _env_float("REFWEAVER_RATE_LIMIT_PUBLISHER", 1.0),
    }


class RateLimiter:
    """Enforce a minimum interval between requests per key."""

    def __init__(self, intervals: dict[str, float]) -> None:
        self._intervals = intervals
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, key: str, min_interval: float | None = None) -> None:
        interval = self._intervals.get(key, 0.0) if min_interval is None else min_interval
        if interval <= 0:
            return

        now = time.monotonic()
        sleep_for = 0.0
        with self._lock:
            last = self._last_request.get(key, 0.0)
            earliest = last + interval
            if now < earliest:
                sleep_for = earliest - now
                self._last_request[key] = now + sleep_for
            else:
                self._last_request[key] = now

        if sleep_for > 0:
            time.sleep(sleep_for)


_GLOBAL_LIMITER = RateLimiter(_default_intervals())


def rate_limit(key: str) -> None:
    _GLOBAL_LIMITER.wait(key)


def rate_limit_url(url: str, default_key: str = "publisher") -> None:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        host = ""

    if host.endswith("doi.org"):
        rate_limit("doi")
        return
    if host == "api.unpaywall.org":
        rate_limit("unpaywall")
        return
    if host == "annas-archive.org":
        rate_limit("annas_archive")
        return

    rate_limit(default_key)
