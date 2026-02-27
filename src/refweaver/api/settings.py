"""API configuration settings."""

import os

from pydantic import BaseModel, Field


class ApiSettings(BaseModel):
    """Settings for the RefWeaver API service."""

    api_title: str = Field(default="RefWeaver API")
    api_version: str = Field(default="0.1.0")
    api_user_header: str = Field(default="X-User-Id")
    api_key_header: str = Field(default="X-API-Key")
    api_key: str | None = Field(default=os.getenv("REFWEAVER_API_KEY"))
    max_input_tokens: int = Field(default=64000)
    run_async_threshold: int = Field(default=2000)
    database_url: str = Field(default=os.getenv("DATABASE_URL", "sqlite:///./refweaver.db"))
    openalex_email: str | None = Field(default=os.getenv("OPENALEX_EMAIL"))
    semantic_scholar_api_key: str | None = Field(default=os.getenv("SEMANTIC_SCHOLAR_API_KEY"))


SETTINGS = ApiSettings()
