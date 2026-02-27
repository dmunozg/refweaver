"""Shared FastAPI dependencies."""

from fastapi import Header

from refweaver.api.errors import http_error
from refweaver.api.settings import SETTINGS


def get_user_id(
    user_id: str | None = Header(default=None, alias=SETTINGS.api_user_header),
) -> str:
    if not user_id:
        raise http_error("missing_user", "Missing user id header", status_code=400)
    return user_id


def verify_api_key(
    api_key: str | None = Header(default=None, alias=SETTINGS.api_key_header),
) -> None:
    if SETTINGS.api_key is None:
        return
    if api_key != SETTINGS.api_key:
        raise http_error("unauthorized", "Invalid API key", status_code=401)
