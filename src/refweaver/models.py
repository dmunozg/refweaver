"""Data models for RefWeaver."""

import contextlib
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from refweaver.http_identity import build_crossref_user_agent


class Sentence(BaseModel):
    """A sentence from a manuscript with reference analysis metadata."""

    text: str = Field(..., description="The sentence text")
    sentence_with_context: str | None = Field(
        default=None,
        description=("Self-contained rewrite of the sentence with context resolved, if available"),
    )
    rewrite_applied: bool = Field(
        default=False,
        description="Whether sentence_with_context was rewritten from the original text",
    )
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
    """Unified article model for all academic search sources.

    Supports BibTeX export with appropriate entry types and fields.
    """

    # Identification
    source: str = Field(
        ...,
        description="Source API: semanticscholar, openalex, scholarly, perplexity",
    )
    external_id: str = Field(..., description="ID from the source API")

    # BibTeX entry type
    entry_type: str = Field(
        default="article",
        description="BibTeX entry type: article, misc, book, inproceedings, etc.",
    )

    # Core metadata
    title: str
    authors: list[str]
    year: int | None = None
    month: int | None = Field(default=None, description="Publication month (1-12)")
    journal: str | None = None
    publication_type: str | None = Field(
        default="article",
        description="article, review, preprint, etc.",
    )

    # Citation details
    volume: str | None = None
    issue: str | None = Field(default=None)
    pages: str | None = None
    doi: str | None = None

    # Publisher info
    publisher: str | None = None

    # Content
    abstract: str | None = None

    # Access
    url: HttpUrl | None = None  # Landing page
    pdf_url: HttpUrl | None = None  # Direct PDF link
    open_access: bool = False

    # For non-article sources (webpages, reports, etc.)
    howpublished: str | None = Field(
        default=None,
        description="How the work was published (e.g., \\url{http://...} for webpages)",
    )
    note: str | None = Field(
        default=None,
        description="Additional notes (e.g., 'Accessed: 2024-01-15')",
    )
    accessed_date: date | None = Field(
        default=None,
        description="Date the source was accessed",
    )

    # Metrics
    citation_count: int | None = None

    # Internal
    retrieved_at: date = Field(default_factory=date.today)

    model_config = {"frozen": True}

    def __str__(self) -> str:
        authors = ", ".join(self.authors[:3]) if self.authors else "Unknown author"
        if self.authors and len(self.authors) > 3:
            authors = f"{self.authors[0]} et al."

        year = str(self.year) if self.year else "n.d."
        title = self.title.rstrip(".") if self.title else "Untitled"

        parts = [f"{authors} ({year}). {title}."]
        if self.journal:
            parts.append(f"{self.journal}.")

        if self.doi:
            parts.append(f"DOI: {self.doi}")
        elif self.url:
            parts.append(f"URL: {self.url}")

        return " ".join(parts)

    def to_bibtex(self, cite_key: str | None = None) -> str:
        """Convert Article to BibTeX format.

        Args:
            cite_key: Optional citation key. If not provided, generates one
                     from first author and year.

        Returns:
            BibTeX formatted string.
        """
        return self._format_bibtex(cite_key)

    def _format_bibtex(self, cite_key: str | None = None) -> str:
        """Internal BibTeX formatting."""
        # Generate cite key if not provided
        if cite_key is None:
            cite_key = self._generate_cite_key()

        # Determine entry type
        entry_type = self.entry_type.lower()

        # Build fields dictionary
        fields: dict[str, str | None] = {}

        # Common fields for most entry types
        if self.title:
            fields["title"] = self._escape_bibtex(self.title)

        if self.authors:
            fields["author"] = " and ".join(self.authors)

        if self.year:
            fields["year"] = str(self.year)

        if self.month:
            fields["month"] = self._month_to_name(self.month)

        if self.doi:
            fields["doi"] = self.doi

        if self.abstract:
            # Abstract is usually too long for BibTeX, but include if present
            fields["abstract"] = self._escape_bibtex(self.abstract[:500])

        # Entry-type specific fields
        if entry_type == "article":
            if self.journal:
                fields["journal"] = self._escape_bibtex(self.journal)
            if self.volume:
                fields["volume"] = self.volume
            if self.issue:
                fields["number"] = self.issue
            if self.pages:
                fields["pages"] = self.pages
            if self.publisher:
                fields["publisher"] = self._escape_bibtex(self.publisher)

        elif entry_type == "misc":
            # For webpages and other non-standard sources
            if self.url:
                fields["howpublished"] = f"\\url{{{self.url!s}}}"
            elif self.howpublished:
                fields["howpublished"] = self.howpublished

            if self.note:
                fields["note"] = self.note
            elif self.accessed_date:
                fields["note"] = f"Accessed: {self.accessed_date.isoformat()}"

        elif entry_type == "inproceedings":
            if self.journal:  # Often used for booktitle in proceedings
                fields["booktitle"] = self._escape_bibtex(self.journal)
            if self.pages:
                fields["pages"] = self.pages
            if self.publisher:
                fields["publisher"] = self._escape_bibtex(self.publisher)

        elif entry_type == "book":
            if self.publisher:
                fields["publisher"] = self._escape_bibtex(self.publisher)

        # Build the BibTeX entry
        lines = [f"@{entry_type}{{{cite_key},"]

        for key, value in fields.items():
            if value:
                lines.append(f"    {key} = {{{value}}},")

        lines.append("}")

        return "\n".join(lines)

    def _generate_cite_key(self) -> str:
        """Generate a citation key from first author and year."""
        parts: list[str] = []

        # First author last name
        if self.authors:
            first_author = self.authors[0]
            # Try to extract last name
            if "," in first_author:
                last_name = first_author.split(",")[0].strip()
            else:
                # Assume "First Last" format
                last_name = first_author.split()[-1]
            parts.append(self._sanitize_key(last_name))
        else:
            parts.append("Unknown")

        # Year
        if self.year:
            parts.append(str(self.year))
        else:
            parts.append("n.d.")  # no date

        # First few words of title if no author/year
        if not self.authors and not self.year and self.title:
            title_words = self.title.split()[:3]
            parts = [self._sanitize_key("_".join(title_words))]

        return "".join(parts)

    def _sanitize_key(self, text: str) -> str:
        """Sanitize text for use in BibTeX citation keys."""
        # Remove special characters, keep alphanumeric and underscore
        sanitized = "".join(c if c.isalnum() else "_" for c in text)
        # Remove multiple underscores
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        # Remove leading/trailing underscores
        return sanitized.strip("_")

    def _escape_bibtex(self, text: str) -> str:
        """Escape special characters for BibTeX."""
        # Characters that need escaping in BibTeX
        escapes = {
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
            "\\": r"\textbackslash{}",
        }

        result = text
        for char, replacement in escapes.items():
            result = result.replace(char, replacement)

        return result

    def _month_to_name(self, month: int) -> str:
        """Convert month number to BibTeX month macro."""
        months = [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ]
        if 1 <= month <= 12:
            return months[month - 1]
        return str(month)

    def enrich_from_crossref(self) -> "Article":
        """Enrich article metadata from CrossRef API using DOI.

        Queries CrossRef API with the article's DOI and updates
        fields with BibTeX-formatted metadata.

        Returns:
            New Article with enriched metadata if successful,
            otherwise returns self unchanged.
        """
        if not self.doi:
            return self

        try:
            import requests

            # Query CrossRef API for BibTeX
            url = f"https://doi.org/{self.doi}"
            headers = {
                "Accept": "application/x-bibtex",
                "User-Agent": build_crossref_user_agent(),
            }

            from refweaver.rate_limit import rate_limit

            rate_limit("crossref")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            bibtex_str = response.text

            # Parse the BibTeX response
            updates = self._parse_bibtex_for_updates(bibtex_str)

            if updates:
                return self.model_copy(update=updates)

        except Exception as e:
            # Log but don't fail - return original
            from loguru import logger

            logger.debug(f"CrossRef enrichment failed for DOI {self.doi}: {e}")

        return self

    def _parse_bibtex_for_updates(self, bibtex_str: str) -> dict[str, Any] | None:
        """Parse BibTeX string and extract fields for updating Article.

        Args:
            bibtex_str: BibTeX formatted string from CrossRef.

        Returns:
            Dictionary of fields to update, or None if parsing fails.
        """
        import re

        updates: dict[str, Any] = {}

        # Extract entry type
        entry_match = re.match(r"@(\w+)\s*{", bibtex_str)
        if entry_match:
            updates["entry_type"] = entry_match.group(1).lower()

        # Extract fields using regex
        # Match: field = {value} or field = "value" or field = value
        field_pattern = r'(\w+)\s*=\s*(?:\{([^}]*)\}|"([^"]*)"|(\d+))'
        matches = re.findall(field_pattern, bibtex_str)

        for match in matches:
            field_name = match[0].lower()
            # Get the non-empty group
            value = next(v for v in match[1:] if v)

            if field_name == "author":
                # Parse "and" separated authors
                authors = [a.strip() for a in value.split(" and ")]
                updates["authors"] = authors

            elif field_name == "title":
                updates["title"] = value

            elif field_name == "year":
                with contextlib.suppress(ValueError):
                    updates["year"] = int(value)

            elif field_name == "month":
                # Try to parse month name or number
                month_map = {
                    "jan": 1,
                    "feb": 2,
                    "mar": 3,
                    "apr": 4,
                    "may": 5,
                    "jun": 6,
                    "jul": 7,
                    "aug": 8,
                    "sep": 9,
                    "oct": 10,
                    "nov": 11,
                    "dec": 12,
                }
                month_lower = value.lower()[:3]
                if month_lower in month_map:
                    updates["month"] = month_map[month_lower]
                else:
                    with contextlib.suppress(ValueError):
                        updates["month"] = int(value)

            elif field_name == "journal":
                updates["journal"] = value

            elif field_name == "volume":
                updates["volume"] = value

            elif field_name == "number":
                updates["issue"] = value

            elif field_name == "pages":
                updates["pages"] = value

            elif field_name == "publisher":
                updates["publisher"] = value

            elif field_name == "doi":
                updates["doi"] = value

            elif field_name == "abstract":
                updates["abstract"] = value

            elif field_name == "url":
                with contextlib.suppress(Exception):
                    updates["url"] = HttpUrl(value)

        return updates if updates else None
