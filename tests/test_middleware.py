from unittest.mock import patch

import pytest
from starlette.requests import ClientDisconnect, Request
from starlette.responses import Response

from refweaver.api.middleware import RequestSizeLimitMiddleware


async def app(scope, receive, send) -> None:
    response = Response("ok", media_type="text/plain")
    await response(scope, receive, send)


@pytest.mark.anyio
async def test_request_disconnect_returns_499() -> None:
    messages = [
        {"type": "http.request", "body": b"partial", "more_body": True},
        {"type": "http.disconnect"},
    ]

    async def receive() -> dict:
        return messages.pop(0)

    received = []

    async def send(message) -> None:
        received.append(message)

    async def raising_body(self) -> bytes:
        raise ClientDisconnect

    with (
        patch("refweaver.api.middleware.SETTINGS") as settings,
        patch.object(Request, "body", raising_body),
    ):
        settings.max_request_bytes = 10_000
        middleware = RequestSizeLimitMiddleware(app)
        scope = {"type": "http", "method": "POST", "path": "/", "headers": []}
        await middleware(scope, receive, send)

    assert any(
        message["type"] == "http.response.start" and message.get("status") == 499
        for message in received
    )


@pytest.mark.anyio
async def test_request_size_limit_allows_small_payload() -> None:
    messages = [
        {"type": "http.request", "body": b"hello", "more_body": False},
    ]

    async def receive() -> dict:
        return messages.pop(0)

    received = []

    async def send(message) -> None:
        received.append(message)

    with patch("refweaver.api.middleware.SETTINGS") as settings:
        settings.max_request_bytes = 10_000
        middleware = RequestSizeLimitMiddleware(app)
        scope = {"type": "http", "method": "POST", "path": "/", "headers": []}
        await middleware(scope, receive, send)

    assert any(
        message["type"] == "http.response.start" and message.get("status") == 200
        for message in received
    )
