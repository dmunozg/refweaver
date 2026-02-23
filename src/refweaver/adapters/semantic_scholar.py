"""Semantic Scholar adapter for RefWeaver."""

from typing import Any

from loguru import logger
from pydantic import HttpUrl
from semanticscholar import SemanticScholar

from refweaver.models import Article
from refweaver.rate_limit import rate_limit
from refweaver.retry import retry_call
from refweaver.timing import run_with_timeout, timed

DEFAULT_SEARCH_TIMEOUT = 15.0  # seconds


class SemanticScholarAdapter:
    """Adapter for the Semantic Scholar API.

    Converts Semantic Scholar responses to unified Article models.
    """

    SOURCE_NAME = "semanticscholar"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Semantic Scholar client.

        Args:
            api_key: Optional API key for higher rate limits.
        """
        if api_key is not None:
            self.client = SemanticScholar(api_key=api_key)
        else:
            self.client = SemanticScholar()

    def _parse_authors(self, authors: list[Any]) -> list[str]:
        """Extract author names from Semantic Scholar author objects."""
        names = []
        for author in authors:
            name = author.get("name") if isinstance(author, dict) else getattr(author, "name", None)
            if name:
                names.append(name)
        return names

    def _to_article(self, paper: Any) -> Article:
        """Convert a Semantic Scholar paper object to an Article.

        Args:
            paper: A Semantic Scholar Paper object or dict.

        Returns:
            An Article model with unified fields.
        """
        # Handle both dict and object responses
        if isinstance(paper, dict):
            return self._to_article_from_dict(paper)

        # Extract authors
        authors = self._parse_authors(getattr(paper, "authors", []) or [])

        # Handle PDF URL with validation
        open_access_pdf: Any = getattr(paper, "openAccessPdf", None)
        pdf_url_input: str | None = None
        if isinstance(open_access_pdf, dict):
            pdf_url_input = open_access_pdf.get("url")

        pdf_url: HttpUrl | None = None
        if pdf_url_input:
            try:
                pdf_url = HttpUrl(pdf_url_input)
            except Exception:
                pdf_url = None

        # Handle year conversion
        year_raw: Any = getattr(paper, "year", None)
        year: int | None = None
        if year_raw is not None:
            try:
                year = int(year_raw)
            except (ValueError, TypeError):
                year = None

        # Handle URL
        url_input: Any = getattr(paper, "url", None)
        url: HttpUrl | None = None
        if url_input:
            try:
                url = HttpUrl(str(url_input))
            except Exception:
                url = None

        # Handle open_access (could be string or bool)
        open_access_raw: Any = getattr(paper, "isOpenAccess", False)
        open_access: bool = bool(open_access_raw) if open_access_raw is not None else False

        # Handle citation_count (could be string or int)
        citation_count_raw: Any = getattr(paper, "citationCount", None)
        citation_count: int | None = None
        if citation_count_raw is not None:
            try:
                citation_count = int(citation_count_raw)
            except (ValueError, TypeError):
                citation_count = None

        # Build Article
        return Article(
            source=self.SOURCE_NAME,
            external_id=str(getattr(paper, "paperId", "") or ""),
            title=str(getattr(paper, "title", "") or ""),
            authors=authors,
            year=year,
            journal=getattr(paper, "venue", None),
            publication_type=getattr(paper, "publicationTypes", ["article"])[0]
            if getattr(paper, "publicationTypes", None)
            else "article",
            volume=getattr(paper, "volume", None),
            issue=getattr(paper, "issue", None),
            pages=getattr(paper, "pages", None),
            doi=getattr(paper, "doi", None),
            abstract=getattr(paper, "abstract", None),
            url=url,
            pdf_url=pdf_url,
            open_access=open_access,
            citation_count=citation_count,
        )

    def _to_article_from_dict(self, paper: dict[str, Any]) -> Article:
        """Convert a Semantic Scholar paper dict to an Article."""
        authors: list[str] = []
        for author in paper.get("authors", []):
            name = author.get("name") if isinstance(author, dict) else str(author)
            if name:
                authors.append(name)

        open_access_pdf: Any = paper.get("openAccessPdf", {})
        pdf_url_str: str | None = None
        if isinstance(open_access_pdf, dict):
            pdf_url_str = open_access_pdf.get("url")

        pdf_url: HttpUrl | None = None
        if pdf_url_str:
            try:
                pdf_url = HttpUrl(pdf_url_str)
            except Exception:
                pdf_url = None

        # Handle year conversion safely
        year_raw: Any = paper.get("year")
        year: int | None = None
        if year_raw is not None:
            try:
                year = int(year_raw)
            except (ValueError, TypeError):
                year = None

        # Handle URL
        url_str: Any = paper.get("url")
        url: HttpUrl | None = None
        if url_str:
            try:
                url = HttpUrl(str(url_str))
            except Exception:
                url = None

        # Handle open_access (could be string or bool)
        open_access_raw: Any = paper.get("isOpenAccess", False)
        open_access: bool = bool(open_access_raw) if open_access_raw is not None else False

        # Handle citation_count (could be string or int)
        citation_count_raw: Any = paper.get("citationCount")
        citation_count: int | None = None
        if citation_count_raw is not None:
            try:
                citation_count = int(citation_count_raw)
            except (ValueError, TypeError):
                citation_count = None

        return Article(
            source=self.SOURCE_NAME,
            external_id=str(paper.get("paperId", "")),
            title=str(paper.get("title", "")),
            authors=authors,
            year=year,
            journal=paper.get("venue"),
            publication_type=paper.get("publicationTypes", ["article"])[0]
            if paper.get("publicationTypes")
            else "article",
            volume=paper.get("volume"),
            issue=paper.get("issue"),
            pages=paper.get("pages"),
            doi=paper.get("doi"),
            abstract=paper.get("abstract"),
            url=url,
            pdf_url=pdf_url,
            open_access=open_access,
            citation_count=citation_count,
        )

    def _do_search(
        self,
        query: str,
        limit: int,
        fields: list[str],
    ) -> list[Article]:
        """Internal search method (without timeout wrapper)."""
        rate_limit("semantic_scholar")
        results: Any = retry_call(
            self.client.search_paper,
            query=query,
            limit=limit,
            fields=fields,
        )
        return [self._to_article(paper) for paper in results[:limit]]

    @timed
    def search(
        self,
        query: str,
        limit: int = 10,
        fields: list[str] | None = None,
        timeout: float = DEFAULT_SEARCH_TIMEOUT,
    ) -> list[Article]:
        """Search for papers on Semantic Scholar.

        Args:
            query: Search query string.
            limit: Maximum number of results to return.
            fields: Optional list of fields to retrieve. If None, uses default
                fields needed for Article conversion.
            timeout: Maximum time to wait for results (default: 15s).

        Returns:
            List of Article objects. Empty list if timeout occurs.
        """
        if fields is None:
            # Note: volume, issue, pages, doi are not available in search endpoint
            # but are available when fetching paper by ID
            fields = [
                "paperId",
                "title",
                "authors",
                "year",
                "venue",
                "publicationTypes",
                "abstract",
                "url",
                "openAccessPdf",
                "isOpenAccess",
                "citationCount",
            ]

        try:
            return run_with_timeout(self._do_search, timeout, query, limit, fields)
        except TimeoutError:
            logger.warning(
                f"Semantic Scholar search timed out after {timeout}s for query: {query[:50]}..."
            )
            return []

    def get_paper_by_doi(self, doi: str) -> Article | None:
        """Fetch a paper by its DOI.

        Args:
            doi: The DOI of the paper.

        Returns:
            An Article if found, None otherwise.
        """
        try:
            rate_limit("semantic_scholar")
            paper: Any = retry_call(self.client.get_paper, doi)
            return self._to_article(paper)
        except Exception:
            return None

    def get_paper_by_id(self, paper_id: str) -> Article | None:
        """Fetch a paper by its Semantic Scholar ID.

        Args:
            paper_id: The Semantic Scholar paper ID.

        Returns:
            An Article if found, None otherwise.
        """
        try:
            rate_limit("semantic_scholar")
            paper: Any = retry_call(self.client.get_paper, f"CorpusId:{paper_id}")
            return self._to_article(paper)
        except Exception:
            return None
