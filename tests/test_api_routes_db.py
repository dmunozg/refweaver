from fastapi import FastAPI
from fastapi.testclient import TestClient

from refweaver.api.routes import runs


def test_runs_route_uses_session_dependency() -> None:
    app = FastAPI()
    app.include_router(runs.router)
    client = TestClient(app)
    response = client.get("/runs/does-not-matter", headers={"x-user-id": "test-user"})
    assert response.status_code == 500
