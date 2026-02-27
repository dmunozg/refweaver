"""Request and response schemas for the API."""

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request payload for analysis."""

    text: str = Field(..., description="Input text to analyze")
    mode: str = Field(default="paragraph", description="sentence|paragraph|document")
    async_mode: bool = Field(default=False, description="Run analysis asynchronously")
    include_markdown: bool = Field(default=True)


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


class HealthResponse(BaseModel):
    """Basic service health response."""

    status: str = Field(default="ok")
