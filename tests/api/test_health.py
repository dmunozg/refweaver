"""Tests for the health endpoint."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient
import pytest

from refweaver.api.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def test_health_reports_db_and_redis_ok(client: TestClient) -> None:
    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection

    old_engine = getattr(app.state, "engine", None)
    app.state.engine = engine
    try:
        with patch("refweaver.api.routes.health.ping_redis", return_value=True):
            response = client.get("/health")
    finally:
        if old_engine is None:
            delattr(app.state, "engine")
        else:
            app.state.engine = old_engine

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["db"]["status"] == "ok"
    assert payload["redis"]["status"] == "ok"


def test_health_reports_db_error_and_503(client: TestClient) -> None:
    engine = MagicMock()
    engine.connect.side_effect = RuntimeError("db down")

    old_engine = getattr(app.state, "engine", None)
    app.state.engine = engine
    try:
        with patch("refweaver.api.routes.health.ping_redis", return_value=True):
            response = client.get("/health")
    finally:
        if old_engine is None:
            delattr(app.state, "engine")
        else:
            app.state.engine = old_engine

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["db"]["status"] == "error"
    assert payload["redis"]["status"] == "ok"
