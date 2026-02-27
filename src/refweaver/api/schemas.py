"""Request and response schemas for the API."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response payload."""

    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, str] | None = Field(default=None)


class HealthResponse(BaseModel):
    """Basic service health response."""

    status: str = Field(default="ok")
