"""Request and response schemas for the API."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalyzeRequest(BaseModel):
    """Request payload for analysis."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., description="Input text to analyze")
    async_mode: bool = Field(default=False, description="Run analysis asynchronously")
    include_markdown: bool = Field(default=True)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must be non-empty")
        return value


class AnalyzeResponse(BaseModel):
    """Response payload for analysis."""

    run_id: str
    status: str
    results: list[dict[str, object]] | None = None
    markdown_report: str | None = None
    job_id: str | None = None
    job_url: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response payload."""

    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, str] | None = Field(default=None)


class HealthCheck(BaseModel):
    """Status of a dependent service."""

    status: str
    message: str | None = None


class HealthResponse(BaseModel):
    """Basic service health response."""

    status: str = Field(default="ok")
    db: HealthCheck | None = None
    redis: HealthCheck | None = None
