"""Semantic Scholar adapter for RefWeaver."""

from typing import List, Optional

from pydantic import HttpUrl
from semanticscholar import SemanticScholar

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

    def _parse_authors(self, authors: list) -> List[str]:
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

    def _to_article(self, paper:dict[str,str]) -> Article:
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

        # validate input
        pdf_url_input = getattr(paper, "openAccessPdf", None).get("url")
        try:
            pdf_url = HttpUrl(pdf_url_input) if pdf_url_input else None
        except Exception:
            pdf_url = None

        # Build Article
        return Article(
            source=self.SOURCE_NAME,
            external_id=getattr(paper, "paperId", "") or "",
            title=getattr(paper, "title", "") or "",
            authors=authors,
            year=getattr(paper, "year", None),
            journal=getattr(paper, "venue", None),
            publication_type=getattr(paper, "publicationTypes", ["article"])[0]
            if getattr(paper, "publicationTypes", None)
            else "article",
            volume=getattr(paper, "volume", None),
            issue=getattr(paper, "issue", None),
            pages=getattr(paper, "pages", None),
            doi=getattr(paper, "doi", None),
            abstract=getattr(paper, "abstract", None),
            url=getattr(paper, "url", None),
            pdf_url=pdf_url
            if isinstance(getattr(paper, "openAccessPdf", None), dict)
            else None,
            open_access=getattr(paper, "isOpenAccess", False) or False,
            citation_count=getattr(paper, "citationCount", None),
        )

    def _to_article_from_dict(self, paper: dict[str, str]) -> Article:
        """Convert a Semantic Scholar paper dict to an Article."""
        authors = []
        for author in paper.get("authors", []):
            if isinstance(author, dict):
                name = author.get("name")
            else:
                name = str(author)
            if name:
                authors.append(name)

        open_access_pdf = paper.get("openAccessPdf", {})
        pdf_url = open_access_pdf.get("url") if isinstance(open_access_pdf, dict) else None

        year_int = int(paper.get("year")) if paper.get("year") is not None else None
        
        url_str = paper.get("url")
        url = HttpUrl(url_str) if url_str else None

        return Article(
            source=self.SOURCE_NAME,
            external_id=paper.get("paperId", ""),
            title=paper.get("title", ""),
            authors=authors,
            year=year_int,
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
            open_access=paper.get("isOpenAccess", False),
            citation_count=paper.get("citationCount"),
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

        results = self.client.search_paper(
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
            paper = self.client.get_paper(doi)
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
            paper = self.client.get_paper(f"CorpusId:{paper_id}")
            return self._to_article(paper)
        except Exception:
            return None
