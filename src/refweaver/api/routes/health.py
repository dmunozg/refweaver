"""Health check endpoint."""

from fastapi import APIRouter, Depends

from refweaver.api.dependencies import rate_limit_user, verify_api_key
from refweaver.api.schemas import HealthResponse

router = APIRouter(
    tags=["health"],
    dependencies=[Depends(verify_api_key), Depends(rate_limit_user)],
)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse()
