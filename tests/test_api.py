"""Tests for the FastAPI scaffolding."""

from fastapi import status
from fastapi.testclient import TestClient

from refweaver.api.errors import http_error
from refweaver.api.main import app
from refweaver.api.schemas import ErrorResponse


def test_health_endpoint_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_http_error_payload_shape() -> None:
    exc = http_error("bad_request", "Invalid input", status_code=status.HTTP_400_BAD_REQUEST)
    assert exc.status_code == status.HTTP_400_BAD_REQUEST
    payload = ErrorResponse.model_validate(exc.detail)
    assert payload.error_code == "bad_request"
    assert payload.message == "Invalid input"
    assert payload.details is None
