"""Semantic Scholar adapter for RefWeaver."""

from typing import Any, List, Optional

from pydantic import HttpUrl
from semanticscholar import SemanticScholar  # type: ignore[import-untyped]

from refweaver.models import Article


class SemanticScholarAdapter:
    """Adapter for the Semantic Scholar API.

    Converts Semantic Scholar responses to unified Article models.
    """

    SOURCE_NAME = "semanticscholar"

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize the Semantic Scholar client.

        Args:
            api_key: Optional API key for higher rate limits.
        """
        self.client = SemanticScholar(api_key=api_key)

    def _parse_authors(self, authors: List[Any]) -> List[str]:
        """Extract author names from Semantic Scholar author objects."""
        names = []
        for author in authors:
            if isinstance(author, dict):
                name = author.get("name")
            else:
                name = getattr(author, "name", None)
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
        pdf_url_input: Optional[str] = None
        if isinstance(open_access_pdf, dict):
            pdf_url_input = open_access_pdf.get("url")

        pdf_url: Optional[HttpUrl] = None
        if pdf_url_input:
            try:
                pdf_url = HttpUrl(pdf_url_input)
            except Exception:
                pdf_url = None

        # Handle year conversion
        year_raw: Any = getattr(paper, "year", None)
        year: Optional[int] = None
        if year_raw is not None:
            try:
                year = int(year_raw)
            except (ValueError, TypeError):
                year = None

        # Handle URL
        url_input: Any = getattr(paper, "url", None)
        url: Optional[HttpUrl] = None
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
        citation_count: Optional[int] = None
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
        authors: List[str] = []
        for author in paper.get("authors", []):
            if isinstance(author, dict):
                name = author.get("name")
            else:
                name = str(author)
            if name:
                authors.append(name)

        open_access_pdf: Any = paper.get("openAccessPdf", {})
        pdf_url_str: Optional[str] = None
        if isinstance(open_access_pdf, dict):
            pdf_url_str = open_access_pdf.get("url")

        pdf_url: Optional[HttpUrl] = None
        if pdf_url_str:
            try:
                pdf_url = HttpUrl(pdf_url_str)
            except Exception:
                pdf_url = None

        # Handle year conversion safely
        year_raw: Any = paper.get("year")
        year: Optional[int] = None
        if year_raw is not None:
            try:
                year = int(year_raw)
            except (ValueError, TypeError):
                year = None

        # Handle URL
        url_str: Any = paper.get("url")
        url: Optional[HttpUrl] = None
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
        citation_count: Optional[int] = None
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

    def search(
        self,
        query: str,
        limit: int = 10,
        fields: Optional[List[str]] = None,
    ) -> List[Article]:
        """Search for papers on Semantic Scholar.

        Args:
            query: Search query string.
            limit: Maximum number of results to return.
            fields: Optional list of fields to retrieve. If None, uses default
                fields needed for Article conversion.

        Returns:
            List of Article objects.
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

        results: Any = self.client.search_paper(
            query=query,
            limit=limit,
            fields=fields,
        )

        return [self._to_article(paper) for paper in results[:limit]]

    def get_paper_by_doi(self, doi: str) -> Optional[Article]:
        """Fetch a paper by its DOI.

        Args:
            doi: The DOI of the paper.

        Returns:
            An Article if found, None otherwise.
        """
        try:
            paper: Any = self.client.get_paper(doi)
            return self._to_article(paper)
        except Exception:
            return None

    def get_paper_by_id(self, paper_id: str) -> Optional[Article]:
        """Fetch a paper by its Semantic Scholar ID.

        Args:
            paper_id: The Semantic Scholar paper ID.

        Returns:
            An Article if found, None otherwise.
        """
        try:
            paper: Any = self.client.get_paper(f"CorpusId:{paper_id}")
            return self._to_article(paper)
        except Exception:
            return None
