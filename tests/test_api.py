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
    with patch("refweaver.api.routes.health.ping_redis", return_value=True):
        response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["db"]["status"] == "ok"
    assert payload["redis"]["status"] == "ok"


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


def test_analyze_async_enqueues_with_user_id(client: TestClient) -> None:
    payload = {
        "text": "This is a test sentence.",
        "async_mode": True,
        "include_markdown": True,
    }
    with patch("refweaver.api.routes.analyze.create_queued_run") as create_run:
        with patch("refweaver.api.routes.analyze.enqueue_job") as enqueue:
            enqueue.return_value = "job-1"
            response = client.post(
                "/analyze",
                headers={"X-User-Id": "user-1"},
                json=payload,
            )
    assert response.status_code == status.HTTP_200_OK
    response_payload = response.json()
    assert response_payload["status"] == "queued"
    enqueue.assert_called_once()
    args, kwargs = enqueue.call_args
    assert args[0] == "refweaver.jobs.analyze_paragraph_job"
    assert args[1] == payload["text"]
    assert kwargs["user_id"] == "user-1"
    assert kwargs["include_markdown"] is True
    assert response_payload["run_id"] == kwargs["run_id"]
    create_run.assert_called_once()
    create_kwargs = create_run.call_args.kwargs
    assert create_kwargs["user_id"] == "user-1"


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


def test_analyze_rejects_input_too_long(client: TestClient) -> None:
    with patch("refweaver.api.routes.analyze.SETTINGS") as settings:
        settings.max_input_tokens = 1
        settings.run_async_threshold = 2000
        response = client.post(
            "/analyze",
            headers={"X-User-Id": "user-1"},
            json={"text": "word word"},
        )
    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    payload = response.json()
    assert payload["detail"]["error_code"] == "input_too_long"


def test_search_requires_user_header(client: TestClient) -> None:
    response = client.post("/search", json={"query": "test"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_jobs_requires_user_header(client: TestClient) -> None:
    response = client.get("/jobs/123")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_jobs_happy_path(client: TestClient) -> None:
    with patch("refweaver.api.routes.jobs.fetch_job") as fetch:
        fetch.return_value = {"job_id": "job-1", "user_id": "user-1"}
        response = client.get("/jobs/job-1", headers={"X-User-Id": "user-1"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["job_id"] == "job-1"


def test_jobs_wrong_user_returns_404(client: TestClient) -> None:
    with patch("refweaver.api.routes.jobs.fetch_job") as fetch:
        fetch.return_value = {"job_id": "job-1", "user_id": "user-2"}
        response = client.get("/jobs/job-1", headers={"X-User-Id": "user-1"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_jobs_missing_user_id_returns_404(client: TestClient) -> None:
    with patch("refweaver.api.routes.jobs.fetch_job") as fetch:
        fetch.return_value = {"job_id": "job-1"}
        response = client.get("/jobs/job-1", headers={"X-User-Id": "user-1"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


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


def test_enrich_happy_path(client: TestClient) -> None:
    with patch("refweaver.api.routes.enrich.ArticleEnricher") as enricher_factory:
        enricher = MagicMock()
        enricher.fill_abstract.return_value = MagicMock(model_dump=MagicMock(return_value={}))
        enricher_factory.return_value = enricher
        response = client.post(
            "/enrich",
            headers={"X-User-Id": "user-1"},
            json={
                "articles": [
                    {
                        "source": "openalex",
                        "external_id": "id-1",
                        "title": "Title",
                        "authors": [],
                    }
                ]
            },
        )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert "results" in payload
    assert len(payload["results"]) == 1


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


def test_report_requires_user_header(client: TestClient) -> None:
    response = client.post("/report", json={"run_id": "run"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_report_happy_path(client: TestClient) -> None:
    session = MagicMock()
    run = MagicMock(user_id="user-1")
    session.get.return_value = run
    query = session.query.return_value
    query.filter_by.return_value.all.return_value = []
    query.filter.return_value = query
    query.all.return_value = []
    session.close.return_value = None

    old_engine = getattr(app.state, "engine", None)
    app.state.engine = object()
    try:
        with patch("refweaver.api.dependencies.get_sessionmaker", return_value=lambda: session):
            with patch("refweaver.api.routes.report.build_run_report", return_value="ok"):
                response = client.post(
                    "/report",
                    headers={"X-User-Id": "user-1"},
                    json={"run_id": "run-1"},
                )
    finally:
        if old_engine is None:
            delattr(app.state, "engine")
        else:
            app.state.engine = old_engine
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert "report" in payload
    assert payload["run_id"] == "run-1"


@pytest.mark.parametrize(
    "payload",
    [
        {"run_id": 123},
        {"run_id": "run-1", "format": "xml"},
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


def test_rate_limit_enforced(client: TestClient) -> None:
    with patch("refweaver.api.dependencies.SETTINGS") as settings:
        settings.rate_limit_per_minute = 1
        settings.rate_limit_backend = "memory"
        settings.api_key = None
        settings.api_user_header = "X-User-Id"
        settings.api_key_header = "X-API-Key"
        with patch("refweaver.api.routes.jobs.fetch_job") as fetch:
            fetch.return_value = {"job_id": "job-1", "user_id": "user-1"}
            response = client.get("/jobs/job-1", headers={"X-User-Id": "user-1"})
            assert response.status_code == status.HTTP_200_OK
            response = client.get("/jobs/job-1", headers={"X-User-Id": "user-1"})
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
            with patch("refweaver.api.routes.jobs.fetch_job") as fetch:
                fetch.return_value = {"job_id": "job-1", "user_id": "user-1"}
                response = client.get("/jobs/job-1", headers={"X-User-Id": "user-1"})
                assert response.status_code == status.HTTP_200_OK
                response = client.get("/jobs/job-1", headers={"X-User-Id": "user-1"})
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


def test_request_size_limit_allows_small_payload(client: TestClient) -> None:
    with patch("refweaver.api.middleware.SETTINGS") as settings:
        settings.max_request_bytes = 10_000
        settings.rate_limit_per_minute = 0
        settings.api_key = None
        settings.api_user_header = "X-User-Id"
        settings.api_key_header = "X-API-Key"
        with patch("refweaver.api.routes.analyze.analyze_paragraph_job") as job:
            job.return_value = {
                "run_id": "run",
                "user_id": "user-1",
                "results": [],
                "markdown_report": None,
            }
            response = client.post(
                "/analyze",
                headers={"X-User-Id": "user-1"},
                json={"text": "This is a test sentence."},
            )
        assert response.status_code == status.HTTP_200_OK
