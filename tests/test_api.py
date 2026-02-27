"""Tests for the FastAPI scaffolding."""

from unittest.mock import MagicMock, patch

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


def test_analyze_requires_user_header() -> None:
    client = TestClient(app)
    response = client.post("/analyze", json={"text": "Hello world"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_analyze_sync_returns_results() -> None:
    client = TestClient(app)
    payload = {
        "text": "This is a test sentence.",
        "include_markdown": False,
    }
    with patch("refweaver.api.routes.analyze.analyze_paragraph_job") as job:
        job.return_value = {"results": [], "markdown_report": None}
        response = client.post("/analyze", headers={"X-User-Id": "user-1"}, json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "completed"
    assert data["results"] is not None


def test_search_requires_user_header() -> None:
    client = TestClient(app)
    response = client.post("/search", json={"query": "test"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_search_basic() -> None:
    client = TestClient(app)
    with patch("refweaver.api.routes.search.UnifiedSearch") as searcher_factory:
        searcher = MagicMock()
        searcher.search.return_value = []
        searcher_factory.return_value = searcher
        response = client.post(
            "/search",
            headers={"X-User-Id": "user-1"},
            json={"query": "test", "limit_per_source": 1, "enrich": False},
        )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert "results" in payload
