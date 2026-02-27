"""API configuration settings."""

from pydantic import BaseModel, Field


class ApiSettings(BaseModel):
    """Settings for the RefWeaver API service."""

    api_title: str = Field(default="RefWeaver API")
    api_version: str = Field(default="0.1.0")
    api_user_header: str = Field(default="X-User-Id")
    api_key: str | None = Field(default=None)
    max_input_tokens: int = Field(default=64000)


SETTINGS = ApiSettings()
