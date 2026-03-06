"""RQ-backed job queue integration."""

from __future__ import annotations

import os
from typing import Any

from redis import Redis
from rq import Queue


def _redis_url() -> str:
    return os.getenv("REFWEAVER_REDIS_URL", "redis://localhost:6379/0")


def get_redis_connection() -> Redis:
    return Redis.from_url(_redis_url())


def get_queue(name: str | None = None) -> Queue:
    queue_name = name if name is not None else os.getenv("REFWEAVER_QUEUE_NAME", "refweaver")
    return Queue(queue_name, connection=get_redis_connection())


def ping_redis() -> bool:
    """Ping Redis and return True on success."""
    redis = get_redis_connection()
    return bool(redis.ping())


def enqueue_job(
    func: str,
    *args: Any,
    user_id: str | None = None,
    **kwargs: Any,
) -> str:
    """Enqueue a job by function path and return job id."""
    job_timeout = os.getenv("REFWEAVER_JOB_TIMEOUT", "1800")
    try:
        timeout = int(job_timeout)
    except ValueError:
        timeout = 1800

    queue = get_queue()
    job = queue.enqueue(func, *args, **kwargs, job_timeout=timeout)
    if user_id is not None:
        job.meta["user_id"] = user_id
        job.save_meta()
    return str(job.id)


def fetch_job(job_id: str) -> dict[str, Any]:
    """Fetch a job and return status/response payload."""
    queue = get_queue()
    job = queue.fetch_job(job_id)
    if job is None:
        return {"status": "missing", "job_id": job_id}

    status = job.get_status()
    payload: dict[str, Any] = {"status": status, "job_id": job_id}
    user_id = job.meta.get("user_id") if hasattr(job, "meta") else None
    if user_id is not None:
        payload["user_id"] = user_id

    if status == "failed":
        payload["error"] = str(job.exc_info)
    elif status == "finished" and isinstance(job.result, dict) and "run_id" in job.result:
        payload["run_id"] = job.result.get("run_id")
        payload["run_url"] = f"/runs/{job.result.get('run_id')}"

    return payload
