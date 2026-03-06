# Queued Run Mode Optional Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow `create_queued_run` to default `mode` to "paragraph" so callers can omit it.

**Architecture:** Adjust the `create_queued_run` signature to provide a default value and keep behavior unchanged for explicit modes. Update any impacted call sites or typing so mypy passes, then verify with API tests.

**Tech Stack:** Python 3.13, SQLAlchemy ORM, pytest, mypy

---

### Task 1: Update `create_queued_run` signature

**Files:**
- Modify: `src/refweaver/db/persist.py`

**Step 1: Write the failing test**

No new test needed; existing API test covers behavior when mode is omitted.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/home/dmunoz/repos/refweaver/.worktrees/analyze-mode-removal/src pytest tests/test_api.py -v`

Expected: FAIL with a mypy or runtime error due to missing `mode` in `create_queued_run`.

**Step 3: Write minimal implementation**

```python
def create_queued_run(
    session: Session,
    *,
    run_id: str,
    user_id: str,
    mode: str = "paragraph",
    input_text: str,
) -> Run:
    ...
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=/home/dmunoz/repos/refweaver/.worktrees/analyze-mode-removal/src pytest tests/test_api.py -v`

Expected: PASS

**Step 5: Run mypy to confirm types**

Run: `mypy src`

Expected: PASS

**Step 6: Commit**

```bash
git add src/refweaver/db/persist.py
git commit -m "refactor: make queued run mode optional"
```
