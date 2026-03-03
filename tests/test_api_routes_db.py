from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from refweaver.api.routes import runs


def test_runs_route_uses_session_dependency() -> None:
    app = FastAPI()
    app.include_router(runs.router)
    client = TestClient(app)
    response = client.get("/runs/does-not-matter", headers={"x-user-id": "test-user"})
    assert response.status_code == 500


class _FakeRun:
    def __init__(self, run_id: str, user_id: str) -> None:
        self.id = run_id
        self.user_id = user_id
        self.mode = "sync"
        self.status = "complete"
        self.input_text = "input"
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.created_at = now
        self.updated_at = now


class _FakeQuery:
    def filter_by(self, **kwargs: Any) -> "_FakeQuery":
        return self

    def filter(self, *args: Any, **kwargs: Any) -> "_FakeQuery":
        return self

    def all(self) -> list[Any]:
        return []

    def __iter__(self) -> Any:
        return iter([])


class _FakeSession:
    def __init__(self, run: _FakeRun | None) -> None:
        self._run = run

    def get(self, model: Any, run_id: str) -> _FakeRun | None:
        return self._run

    def query(self, model: Any) -> _FakeQuery:
        return _FakeQuery()


def test_runs_happy_path() -> None:
    app = FastAPI()
    app.include_router(runs.router)
    client = TestClient(app)
    fake_session = _FakeSession(_FakeRun("run-1", "user-1"))

    def _fake_session_override() -> Any:
        yield fake_session

    app.dependency_overrides[runs.get_db_session] = _fake_session_override
    response = client.get("/runs/run-1", headers={"x-user-id": "user-1"})

    assert response.status_code == 200
    assert response.json()["run"]["id"] == "run-1"


def test_runs_wrong_user_returns_404() -> None:
    app = FastAPI()
    app.include_router(runs.router)
    client = TestClient(app)
    fake_session = _FakeSession(_FakeRun("run-1", "user-2"))

    def _fake_session_override() -> Any:
        yield fake_session

    app.dependency_overrides[runs.get_db_session] = _fake_session_override
    response = client.get("/runs/run-1", headers={"x-user-id": "user-1"})

    assert response.status_code == 404
