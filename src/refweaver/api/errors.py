"""API error helpers."""

from fastapi import HTTPException, status

from refweaver.api.schemas import ErrorResponse


def http_error(
    error_code: str,
    message: str,
    *,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: dict[str, str] | None = None,
) -> HTTPException:
    """Return an HTTPException with a standardized error payload."""
    payload = ErrorResponse(error_code=error_code, message=message, details=details)
    return HTTPException(status_code=status_code, detail=payload.model_dump())
