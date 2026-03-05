"""Custom FastAPI middleware."""

from __future__ import annotations

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response

from refweaver.api.settings import SETTINGS


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Enforce max request size for incoming requests."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        limit = SETTINGS.max_request_bytes
        if limit <= 0:
            return await call_next(request)

        if request.headers.get("content-length") is not None:
            try:
                content_length = int(request.headers["content-length"])
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error_code": "invalid_content_length",
                        "message": "Invalid content-length header",
                        "details": None,
                    },
                )
            if content_length > limit:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "error_code": "request_too_large",
                        "message": "Request body exceeds size limit",
                        "details": {"max_bytes": str(limit)},
                    },
                )

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
        if len(body) > limit:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error_code": "request_too_large",
                    "message": "Request body exceeds size limit",
                    "details": {"max_bytes": str(limit)},
                },
            )

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(request.scope, receive=receive)
        return await call_next(request)
