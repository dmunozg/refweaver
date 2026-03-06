"""Health check endpoint."""

from fastapi import APIRouter, Request
from sqlalchemy import text

from refweaver.api.schemas import HealthCheck, HealthResponse
from refweaver.queue import ping_redis

router = APIRouter(tags=["health"])


def _check_db(engine: object) -> HealthCheck:
    if engine is None:
        return HealthCheck(status="error", message="Database engine not initialized")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return HealthCheck(status="ok")
    except Exception as exc:  # pragma: no cover - depends on driver
        return HealthCheck(status="error", message=str(exc))


def _check_redis() -> HealthCheck:
    try:
        if ping_redis():
            return HealthCheck(status="ok")
        return HealthCheck(status="error", message="Redis ping failed")
    except Exception as exc:  # pragma: no cover - depends on driver
        return HealthCheck(status="error", message=str(exc))


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Return service health status."""
    engine = getattr(request.app.state, "engine", None)
    db_status = _check_db(engine)
    redis_status = _check_redis()
    overall = "ok" if db_status.status == "ok" and redis_status.status == "ok" else "error"
    return HealthResponse(status=overall, db=db_status, redis=redis_status)
