"""Data models for RefWeaver."""

from datetime import date

from pydantic import BaseModel, Field, HttpUrl


class Sentence(BaseModel):
    """A sentence from a manuscript with reference analysis metadata."""

    text: str = Field(..., description="The sentence text")
    needs_reference: bool = Field(
        ...,
        description="Whether this sentence requires a reference/citation",
    )
    reason: str = Field(
        ...,
        description="Explanation for why the sentence needs or doesn't need a reference",
    )

    model_config = {"frozen": True}


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
    authors: list[str]
    year: int | None = None
    journal: str | None = None
    publication_type: str | None = Field(
        default="article",
        description="article, review, preprint, etc.",
    )

    # Citation details
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None

    # Content
    abstract: str | None = None

    # Access
    url: HttpUrl | None = None  # Landing page
    pdf_url: HttpUrl | None = None  # Direct PDF link
    open_access: bool = False

    # Metrics
    citation_count: int | None = None

    # Internal
    retrieved_at: date = Field(default_factory=date.today)

    model_config = {"frozen": True}
