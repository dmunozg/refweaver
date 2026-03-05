from unittest.mock import patch

from fastapi.testclient import TestClient

from refweaver.api.main import create_app


def test_engine_initialized_once_on_startup() -> None:
    with patch("refweaver.api.main.get_engine") as mocked:
        app = create_app()
        with TestClient(app):
            pass
        assert mocked.call_count == 1
