"""Data models for RefWeaver."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class Article(BaseModel):
    """Unified article model for all academic search sources."""

    # Identification
    source: str = Field(
        ...,
        description="Source API: semanticscholar, openalex, or scholarly",
    )
    external_id: str = Field(..., description="ID from the source API")

    # Core metadata
    title: str
    authors: List[str]
    year: Optional[int] = None
    journal: Optional[str] = None
    publication_type: Optional[str] = Field(
        default="article",
        description="article, review, preprint, etc.",
    )

    # Citation details
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None

    # Content
    abstract: Optional[str] = None

    # Access
    url: Optional[HttpUrl] = None  # Landing page
    pdf_url: Optional[HttpUrl] = None  # Direct PDF link
    open_access: bool = False

    # Metrics
    citation_count: Optional[int] = None

    # Internal
    retrieved_at: date = Field(default_factory=date.today)

    model_config = {"frozen": True}
