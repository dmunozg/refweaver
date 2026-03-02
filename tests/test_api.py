"""Tests for the FastAPI scaffolding."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from refweaver.api.errors import http_error
from refweaver.api.main import app
from refweaver.api.schemas import ErrorResponse


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def test_health_endpoint_ok(client: TestClient) -> None:
    response = client.get("/health", headers={"X-User-Id": "user-1"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_http_error_payload_shape() -> None:
    exc = http_error("bad_request", "Invalid input", status_code=status.HTTP_400_BAD_REQUEST)
    assert exc.status_code == status.HTTP_400_BAD_REQUEST
    payload = ErrorResponse.model_validate(exc.detail)
    assert payload.error_code == "bad_request"
    assert payload.message == "Invalid input"
    assert payload.details is None


def test_analyze_requires_user_header(client: TestClient) -> None:
    response = client.post("/analyze", json={"text": "Hello world"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_analyze_sync_returns_results(client: TestClient) -> None:
    payload = {
        "text": "This is a test sentence.",
        "include_markdown": False,
    }
    with patch("refweaver.api.routes.analyze.analyze_paragraph_job") as job:
        job.return_value = {
            "run_id": "run",
            "user_id": "user-1",
            "results": [],
            "markdown_report": None,
        }
        response = client.post("/analyze", headers={"X-User-Id": "user-1"}, json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "completed"
    assert data["results"] is not None


def test_analyze_rejects_empty_text(client: TestClient) -> None:
    response = client.post(
        "/analyze",
        headers={"X-User-Id": "user-1"},
        json={"text": "   "},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_analyze_rejects_mode_field(client: TestClient) -> None:
    response = client.post(
        "/analyze",
        headers={"X-User-Id": "user-1"},
        json={"text": "This is a test sentence.", "mode": "paragraph"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_search_requires_user_header(client: TestClient) -> None:
    response = client.post("/search", json={"query": "test"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_jobs_requires_user_header(client: TestClient) -> None:
    response = client.get("/jobs/123")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_search_basic(client: TestClient) -> None:
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


def test_search_rejects_empty_query(client: TestClient) -> None:
    response = client.post(
        "/search",
        headers={"X-User-Id": "user-1"},
        json={"query": "   "},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_enrich_requires_user_header(client: TestClient) -> None:
    response = client.post("/enrich", json={"articles": []})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_report_requires_user_header(client: TestClient) -> None:
    response = client.post("/report", json={"run_id": "run"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_rate_limit_enforced(client: TestClient) -> None:
    with patch("refweaver.api.dependencies.SETTINGS") as settings:
        settings.rate_limit_per_minute = 1
        settings.rate_limit_backend = "memory"
        settings.api_key = None
        settings.api_user_header = "X-User-Id"
        settings.api_key_header = "X-API-Key"
        response = client.get("/health", headers={"X-User-Id": "user-1"})
        assert response.status_code == status.HTTP_200_OK
        response = client.get("/health", headers={"X-User-Id": "user-1"})
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_rate_limit_redis_backend(client: TestClient) -> None:
    with patch("refweaver.api.dependencies.SETTINGS") as settings:
        settings.rate_limit_per_minute = 1
        settings.rate_limit_backend = "redis"
        settings.api_key = None
        settings.api_user_header = "X-User-Id"
        settings.api_key_header = "X-API-Key"
        with patch("refweaver.queue.get_redis_connection") as get_redis:
            redis = MagicMock()
            redis.incr.side_effect = [1, 2]
            get_redis.return_value = redis
            response = client.get("/health", headers={"X-User-Id": "user-1"})
            assert response.status_code == status.HTTP_200_OK
            response = client.get("/health", headers={"X-User-Id": "user-1"})
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_request_size_limit_enforced(client: TestClient) -> None:
    with patch("refweaver.api.middleware.SETTINGS") as settings:
        settings.max_request_bytes = 10
        settings.rate_limit_per_minute = 0
        settings.api_key = None
        settings.api_user_header = "X-User-Id"
        settings.api_key_header = "X-API-Key"
        response = client.post(
            "/analyze",
            headers={"X-User-Id": "user-1", "Content-Length": "999"},
            json={"text": "This is a test sentence."},
        )
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


def test_request_size_limit_enforced_without_length(client: TestClient) -> None:
    with patch("refweaver.api.middleware.SETTINGS") as settings:
        settings.max_request_bytes = 10
        settings.rate_limit_per_minute = 0
        settings.api_key = None
        settings.api_user_header = "X-User-Id"
        settings.api_key_header = "X-API-Key"
        response = client.post(
            "/analyze",
            headers={"X-User-Id": "user-1"},
            json={"text": "This is a test sentence."},
        )
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
