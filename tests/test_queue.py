from __future__ import annotations

from typing import Any

from pytest import MonkeyPatch

from refweaver.queue import enqueue_job


def test_enqueue_job_sets_user_id_metadata(monkeypatch: MonkeyPatch) -> None:
    class _Job:
        def __init__(self) -> None:
            self.id = "job-1"
            self.meta: dict[str, str] = {}
            self.saved = False

        def save_meta(self) -> None:
            self.saved = True

    class _Queue:
        def __init__(self, job: _Job) -> None:
            self._job = job

        def enqueue(self, *_args: Any, **_kwargs: Any):
            return self._job

    job = _Job()
    monkeypatch.setattr("refweaver.queue.get_queue", lambda: _Queue(job))

    job_id = enqueue_job("refweaver.jobs.analyze_paragraph_job", "text", user_id="user-1")

    assert job_id == "job-1"
    assert job.meta["user_id"] == "user-1"
    assert job.saved is True


def test_enqueue_job_allows_metadata_user_id_override(monkeypatch: MonkeyPatch) -> None:
    class _Job:
        def __init__(self) -> None:
            self.id = "job-1"
            self.meta: dict[str, str] = {}
            self.saved = False

        def save_meta(self) -> None:
            self.saved = True

    class _Queue:
        def __init__(self, job: _Job) -> None:
            self._job = job

        def enqueue(self, *_args: Any, **_kwargs: Any):
            return self._job

    job = _Job()
    monkeypatch.setattr("refweaver.queue.get_queue", lambda: _Queue(job))

    job_id = enqueue_job(
        "refweaver.jobs.analyze_paragraph_job",
        "text",
        user_id="worker-user",
        metadata_user_id="api-user",
    )

    assert job_id == "job-1"
    assert job.meta["user_id"] == "api-user"
    assert job.saved is True
