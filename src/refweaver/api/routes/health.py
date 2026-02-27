"""Health check endpoint."""

from fastapi import APIRouter

from refweaver.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse()
