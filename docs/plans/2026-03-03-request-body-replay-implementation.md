# Request Body Replay Middleware Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the private request body mutation with a documented ASGI receive wrapper, and add tests including a mid-request disconnect that returns a 499 response.

**Architecture:** Buffer the request body once in `RequestSizeLimitMiddleware.dispatch`, then construct a new `Request(scope, receive=...)` that replays the buffered bytes. Add a unit-style ASGI test that feeds `http.request` then `http.disconnect` and asserts a 499 response.

**Tech Stack:** FastAPI/Starlette, pytest, unittest.mock.

---

### Task 1: Add a failing test for buffering behavior

**Files:**
- Modify: `tests/test_api.py`

**Step 1: Write the failing test**

```python
def test_request_size_limit_allows_small_payload(client: TestClient) -> None:
    with patch("refweaver.api.middleware.SETTINGS") as settings:
        settings.max_request_bytes = 10_000
        settings.rate_limit_per_minute = 0
        settings.api_key = None
        settings.api_user_header = "X-User-Id"
        settings.api_key_header = "X-API-Key"
        response = client.post(
            "/analyze",
            headers={"X-User-Id": "user-1"},
            json={"text": "This is a test sentence."},
        )
        assert response.status_code == status.HTTP_200_OK
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_request_size_limit_allows_small_payload -v`

Expected: FAIL (if middleware changes break normal body handling).

**Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: add coverage for small request payload"
```

### Task 2: Add a failing test for mid-request disconnect

**Files:**
- Create: `tests/test_middleware.py`

**Step 1: Write the failing test**

```python
import pytest
from starlette.responses import Response

from refweaver.api.middleware import RequestSizeLimitMiddleware


async def app(scope, receive, send) -> None:
    response = Response("ok", media_type="text/plain")
    await response(scope, receive, send)


@pytest.mark.asyncio
async def test_request_disconnect_returns_499() -> None:
    async def receive():
        yield {"type": "http.request", "body": b"partial", "more_body": True}
        yield {"type": "http.disconnect"}

    received = []

    async def send(message: dict) -> None:
        received.append(message)

    middleware = RequestSizeLimitMiddleware(app)
    scope = {"type": "http", "method": "POST", "path": "/", "headers": []}

    await middleware(scope, receive().__anext__, send)

    assert any(
        message["type"] == "http.response.start"
        and message.get("status") == 499
        for message in received
    )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_middleware.py::test_request_disconnect_returns_499 -v`

Expected: FAIL (until middleware catches disconnect and returns 499).

**Step 3: Commit**

```bash
git add tests/test_middleware.py
git commit -m "test: cover mid-request disconnect handling"
```

### Task 3: Implement receive wrapper and disconnect handling

**Files:**
- Modify: `src/refweaver/api/middleware.py`

**Step 1: Write minimal implementation**

```python
from starlette.requests import ClientDisconnect


        try:
            body = await request.body()
        except ClientDisconnect:
            return JSONResponse(
                status_code=499,
                content={
                    "error_code": "client_disconnected",
                    "message": "Client disconnected while streaming request body",
                    "details": None,
                },
            )

        async def receive() -> dict:
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(request.scope, receive=receive)
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_api.py::test_request_size_limit_allows_small_payload -v`
Expected: PASS

Run: `pytest tests/test_api.py::test_request_size_limit_enforced -v`
Expected: PASS

Run: `pytest tests/test_api.py::test_request_size_limit_enforced_without_length -v`
Expected: PASS

Run: `pytest tests/test_middleware.py::test_request_disconnect_returns_499 -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/refweaver/api/middleware.py tests/test_api.py tests/test_middleware.py
git commit -m "fix: replay buffered request body via receive wrapper"
```

### Task 4: Optional full test suite

**Files:**
- None

**Step 1: Run full suite**

Run: `pytest`

Expected: PASS
