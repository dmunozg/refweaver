# API Endpoint Coverage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add happy-path and malicious-payload tests for API endpoints lacking success-path coverage, including 404 isolation for wrong-user access to runs/jobs.

**Architecture:** Use FastAPI `TestClient` with dependency overrides or route-level mocks to simulate data access without a real DB. Add malformed payload tests via request validation (422) and explicit wrong-user tests that return 404 to avoid existence leaks.

**Tech Stack:** Python 3.13, pytest, FastAPI TestClient

---

### Task 1: Add happy-path + malformed payload tests for /enrich and /report

**Files:**
- Modify: `tests/test_api.py`

**Step 1: Write the failing tests**

```python
def test_enrich_happy_path(client: TestClient) -> None:
    with patch("refweaver.api.routes.enrich.enrich_articles") as enrich:
        enrich.return_value = []
        response = client.post(
            "/enrich",
            headers={"X-User-Id": "user-1"},
            json={"articles": []},
        )
    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.json()


def test_report_happy_path(client: TestClient) -> None:
    with patch("refweaver.api.routes.report.generate_report") as report:
        report.return_value = {"report": "ok"}
        response = client.post(
            "/report",
            headers={"X-User-Id": "user-1"},
            json={"run_id": "run-1"},
        )
    assert response.status_code == status.HTTP_200_OK
    assert "report" in response.json()


@pytest.mark.parametrize(
    "payload",
    [
        {"articles": "not-a-list"},
        {"articles": [{"title": "bad\u0000title"}]},
        {},
    ],
)
def test_enrich_rejects_malformed_payload(client: TestClient, payload: dict[str, object]) -> None:
    response = client.post(
        "/enrich",
        headers={"X-User-Id": "user-1"},
        json=payload,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "payload",
    [
        {"run_id": 123},
        {"run_id": "\u0000bad"},
        {},
    ],
)
def test_report_rejects_malformed_payload(client: TestClient, payload: dict[str, object]) -> None:
    response = client.post(
        "/report",
        headers={"X-User-Id": "user-1"},
        json=payload,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py::test_enrich_happy_path -v`
Expected: FAIL (missing mocks / response shape mismatches)

**Step 3: Write minimal implementation**

```python
# Ensure correct patch targets and response shape based on actual route logic.
# Adjust mocked return values to match route response keys.
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py::test_enrich_happy_path -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_api.py
git commit -m "test: add enrich/report endpoint coverage"
```

### Task 2: Add happy-path + wrong-user tests for /runs/{run_id}

**Files:**
- Modify: `tests/test_api_routes_db.py` (or create `tests/test_api_routes_security.py`)

**Step 1: Write the failing tests**

```python
def test_runs_happy_path() -> None:
    app = FastAPI()
    app.include_router(runs.router)
    client = TestClient(app)
    with patch("refweaver.api.routes.runs.fetch_run") as fetch:
        fetch.return_value = {"run_id": "run-1", "user_id": "user-1"}
        response = client.get("/runs/run-1", headers={"x-user-id": "user-1"})
    assert response.status_code == 200
    assert response.json()["run_id"] == "run-1"


def test_runs_wrong_user_returns_404() -> None:
    app = FastAPI()
    app.include_router(runs.router)
    client = TestClient(app)
    with patch("refweaver.api.routes.runs.fetch_run") as fetch:
        fetch.return_value = {"run_id": "run-1", "user_id": "user-2"}
        response = client.get("/runs/run-1", headers={"x-user-id": "user-1"})
    assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_routes_db.py::test_runs_happy_path -v`
Expected: FAIL (route likely returns 500/403 or different shape)

**Step 3: Write minimal implementation**

```python
# Adjust mock return shape or patch target to match actual route logic.
# If route does not inspect user_id, patch a lower-level helper that does.
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api_routes_db.py::test_runs_happy_path -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_api_routes_db.py
git commit -m "test: cover runs endpoint isolation"
```

### Task 3: Add happy-path + wrong-user tests for /jobs/{job_id}

**Files:**
- Modify: `tests/test_api.py` or create `tests/test_api_routes_security.py`

**Step 1: Write the failing tests**

```python
def test_jobs_happy_path(client: TestClient) -> None:
    with patch("refweaver.api.routes.jobs.fetch_job") as fetch:
        fetch.return_value = {"job_id": "job-1", "user_id": "user-1"}
        response = client.get("/jobs/job-1", headers={"X-User-Id": "user-1"})
    assert response.status_code == 200
    assert response.json()["job_id"] == "job-1"


def test_jobs_wrong_user_returns_404(client: TestClient) -> None:
    with patch("refweaver.api.routes.jobs.fetch_job") as fetch:
        fetch.return_value = {"job_id": "job-1", "user_id": "user-2"}
        response = client.get("/jobs/job-1", headers={"X-User-Id": "user-1"})
    assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py::test_jobs_happy_path -v`
Expected: FAIL (route likely returns 404 or different shape)

**Step 3: Write minimal implementation**

```python
# Adjust mock return values to match job payload shape and route behavior.
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py::test_jobs_happy_path -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_api.py
git commit -m "test: cover jobs endpoint isolation"
```

### Task 4: Run full test suite

**Files:**
- None

**Step 1: Run tests**

Run: `pytest`
Expected: PASS

**Step 2: Commit (if needed)**

```bash
git status
```
Expected: clean working tree
