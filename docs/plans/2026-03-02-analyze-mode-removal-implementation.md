# Analyze Mode Removal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the `mode` parameter from the `/analyze` request schema and reject requests that include it, aligning the API with the actual paragraph-only analysis behavior.

**Architecture:** Update the API request schema to drop `mode`, remove request-time validation and persistence usage in the `/analyze` route, and adjust tests to expect 422 when `mode` is provided. Keep downstream analysis and persistence unchanged (jobs still store `mode="paragraph"`).

**Tech Stack:** FastAPI, Pydantic, pytest, SQLAlchemy (for persistence), Python 3.13.

---

### Task 1: Add a failing test for rejecting `mode`

**Files:**
- Modify: `tests/test_api.py`

**Step 1: Write the failing test**

```python
def test_analyze_rejects_mode_field(client: TestClient) -> None:
    response = client.post(
        "/analyze",
        headers={"X-User-Id": "user-1"},
        json={"text": "This is a test sentence.", "mode": "paragraph"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_analyze_rejects_mode_field -v`
Expected: FAIL because `mode` is currently accepted.

**Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: cover analyze mode removal"
```

### Task 2: Remove `mode` from request schema

**Files:**
- Modify: `src/refweaver/api/schemas.py`

**Step 1: Write minimal implementation**

Remove the `mode` field and its validator from `AnalyzeRequest`.

```python
class AnalyzeRequest(BaseModel):
    """Request payload for analysis."""

    text: str = Field(..., description="Input text to analyze")
    async_mode: bool = Field(default=False, description="Run analysis asynchronously")
    include_markdown: bool = Field(default=True)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must be non-empty")
        return value
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_api.py::test_analyze_rejects_mode_field -v`
Expected: PASS with 422 status.

**Step 3: Commit**

```bash
git add src/refweaver/api/schemas.py
git commit -m "refactor: drop analyze mode from request"
```

### Task 3: Remove mode usage from `/analyze` route

**Files:**
- Modify: `src/refweaver/api/routes/analyze.py`

**Step 1: Write minimal implementation**

Remove the `mode` validation block and stop passing `mode` to `create_queued_run`.

```python
    validate_text_length(payload.text, max_tokens=SETTINGS.max_input_tokens)

    run_id = uuid4().hex
    if payload.async_mode or len(payload.text) > SETTINGS.run_async_threshold:
        create_queued_run(
            session,
            run_id=run_id,
            user_id=user_id,
            input_text=payload.text,
        )
```

**Step 2: Run test suite for API**

Run: `pytest tests/test_api.py -v`
Expected: PASS.

**Step 3: Commit**

```bash
git add src/refweaver/api/routes/analyze.py
git commit -m "refactor: remove mode handling from analyze route"
```

### Task 4: Verify no remaining request-level references to `mode`

**Files:**
- Modify: (none expected)

**Step 1: Search for `mode` usage in API request handling**

Run: `rg "AnalyzeRequest|/analyze|mode" src/refweaver/api -g"*.py"`
Expected: No remaining references to `AnalyzeRequest.mode` or `/analyze` mode validation.

**Step 2: Run full tests (optional)**

Run: `pytest`
Expected: PASS.

**Step 3: Commit**

```bash
git add .
git commit -m "chore: finalize analyze mode removal"
```
