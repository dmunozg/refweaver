# Shared API Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reuse a single SQLAlchemy engine for the FastAPI app lifecycle and create per-request sessions from it.

**Architecture:** Create the engine at API startup, store it on `app.state`, and provide a request-scoped dependency that yields a session bound to that engine. Routes use the dependency instead of calling `get_session`.

**Tech Stack:** FastAPI, SQLAlchemy, pytest

---

### Task 1: Add request-scoped session dependency

**Files:**
- Modify: `src/refweaver/api/dependencies.py`
- Test: `tests/test_api_db_session.py`

**Step 1: Write the failing test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from refweaver.api.dependencies import get_db_session


def test_get_db_session_requires_engine() -> None:
    app = FastAPI()

    @app.get("/health")
    def _health() -> None:
        return None

    client = TestClient(app)

    @app.get("/db-check")
    def _db_check(session=Depends(get_db_session)) -> None:  # type: ignore[valid-type]
        return None

    response = client.get("/db-check")
    assert response.status_code == 500
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_db_session.py::test_get_db_session_requires_engine -v`
Expected: FAIL because `get_db_session` does not exist yet.

**Step 3: Write minimal implementation**

```python
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from refweaver.db.session import get_sessionmaker


def get_db_session(request: Request) -> Iterator[Session]:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(status_code=500, detail="Database engine is not initialized")

    maker = get_sessionmaker(engine)
    session = maker()
    try:
        yield session
    finally:
        session.close()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_db_session.py::test_get_db_session_requires_engine -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/refweaver/api/dependencies.py tests/test_api_db_session.py
git commit -m "feat: add db session dependency for API"
```

### Task 2: Initialize shared engine on app startup

**Files:**
- Modify: `src/refweaver/api/main.py`
- Modify: `src/refweaver/db/session.py`
- Test: `tests/test_api_engine_lifecycle.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from unittest.mock import patch

from refweaver.api.main import create_app


def test_engine_initialized_once_on_startup() -> None:
    with patch("refweaver.api.main.get_engine") as mocked:
        app = create_app()
        with TestClient(app):
            pass
        assert mocked.call_count == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_engine_lifecycle.py::test_engine_initialized_once_on_startup -v`
Expected: FAIL because startup hook is missing.

**Step 3: Write minimal implementation**

```python
from refweaver.db.session import get_engine


@app.on_event("startup")
def _startup() -> None:
    app.state.engine = get_engine(SETTINGS.database_url)


@app.on_event("shutdown")
def _shutdown() -> None:
    engine = getattr(app.state, "engine", None)
    if engine is not None:
        engine.dispose()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_engine_lifecycle.py::test_engine_initialized_once_on_startup -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/refweaver/api/main.py src/refweaver/db/session.py tests/test_api_engine_lifecycle.py
git commit -m "feat: initialize shared engine in API startup"
```

### Task 3: Wire API routes to use dependency

**Files:**
- Modify: `src/refweaver/api/routes/analyze.py`
- Modify: `src/refweaver/api/routes/report.py`
- Modify: `src/refweaver/api/routes/runs.py`
- Test: `tests/test_api_routes_db.py`

**Step 1: Write the failing test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from refweaver.api.routes import runs


def test_runs_route_uses_session_dependency() -> None:
    app = FastAPI()
    app.include_router(runs.router)
    client = TestClient(app)
    response = client.get("/runs/does-not-matter")
    assert response.status_code == 500
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_routes_db.py::test_runs_route_uses_session_dependency -v`
Expected: FAIL because the route still creates its own session.

**Step 3: Write minimal implementation**

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from refweaver.api.dependencies import get_db_session


def get_run(..., session: Session = Depends(get_db_session)) -> dict[str, object]:
    run = session.get(Run, run_id)
    ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_routes_db.py::test_runs_route_uses_session_dependency -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/refweaver/api/routes/analyze.py src/refweaver/api/routes/report.py src/refweaver/api/routes/runs.py tests/test_api_routes_db.py
git commit -m "refactor: use shared db session dependency"
```

### Task 4: Update documentation and verify

**Files:**
- Modify: `docs/API.md`

**Step 1: Write doc update**

```markdown
- Database connections are pooled via a shared engine created at API startup.
```

**Step 2: Run tests**

Run: `pytest tests/test_api_db_session.py tests/test_api_engine_lifecycle.py tests/test_api_routes_db.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add docs/API.md
git commit -m "docs: note shared engine lifecycle"
```
