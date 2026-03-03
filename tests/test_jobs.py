"""Jobs tests."""

from __future__ import annotations

from contextlib import contextmanager

from refweaver import jobs


def test_analyze_paragraph_job_uses_session_scope_and_closes_session(
    monkeypatch,
) -> None:
    session_scope_called = False
    session_closed = False
    captured_url: str | None = None
    engine = object()

    class FakeSession:
        def close(self) -> None:
            nonlocal session_closed
            session_closed = True

    @contextmanager
    def fake_session_scope(scope_engine):
        nonlocal session_scope_called
        session_scope_called = True
        assert scope_engine is engine
        session = FakeSession()
        try:
            yield session
        finally:
            session.close()

    def fake_get_engine_cached(database_url: str):
        nonlocal captured_url
        captured_url = database_url
        return engine

    def fake_create_queued_run(session, **_kwargs):
        assert isinstance(session, FakeSession)

    def fake_persist_run_results(session, **_kwargs):
        assert isinstance(session, FakeSession)

    def fake_analyze_paragraph_with_evidence(_paragraph: str):
        return []

    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setattr(jobs, "get_engine_cached", fake_get_engine_cached)
    monkeypatch.setattr(jobs, "session_scope", fake_session_scope)
    monkeypatch.setattr(jobs, "create_queued_run", fake_create_queued_run)
    monkeypatch.setattr(jobs, "persist_run_results", fake_persist_run_results)
    monkeypatch.setattr(
        jobs, "analyze_paragraph_with_evidence", fake_analyze_paragraph_with_evidence
    )

    jobs.analyze_paragraph_job(
        "Example paragraph.",
        run_id="run-1",
        user_id="user-1",
        include_markdown=False,
    )

    assert session_scope_called is True
    assert session_closed is True
    assert captured_url == "sqlite:///./test.db"
