from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from refweaver.api.dependencies import get_db_session


def test_get_db_session_requires_engine() -> None:
    app = FastAPI()

    @app.get("/health")
    def _health() -> None:
        return None

    client = TestClient(app)

    @app.get("/db-check")
    def _db_check(session=Depends(get_db_session)) -> None:  # type: ignore[valid-type]
        return None

    response = client.get("/db-check")
    assert response.status_code == 500
