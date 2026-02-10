"""OpenAlex adapter for RefWeaver."""

from typing import Any

from loguru import logger
from pyalex import Works
from pydantic import HttpUrl

from refweaver.models import Article
from refweaver.timing import run_with_timeout, timed

DEFAULT_SEARCH_TIMEOUT = 15.0  # seconds


class OpenAlexAdapter:
    """Adapter for the OpenAlex API.

    Converts OpenAlex responses to unified Article models.
    """

    SOURCE_NAME = "openalex"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the OpenAlex client.

        Args:
            api_key: Optional API key for higher rate limits (email address).
        """
        if api_key:
            from pyalex import config as pyalex_config
            pyalex_config.email = api_key

    def _parse_authors(self, authors: list[Any]) -> list[str]:
        """Extract author names from OpenAlex author objects."""
        names = []
        for author in authors:
            if isinstance(author, dict):
                # Handle authorship object
                author_data = author.get("author", {})
                if isinstance(author_data, dict):
                    name = author_data.get("display_name")
                else:
                    name = getattr(author_data, "display_name", None)
            else:
                name = getattr(author, "display_name", None)
            if name:
                names.append(name)
        return names

    def _get_doi(self, work: dict[str, Any]) -> str | None:
        """Extract DOI from OpenAlex work."""
        doi: Any = work.get("doi")
        if doi:
            # OpenAlex returns full URL like "https://doi.org/10.1234/example"
            # We want just the DOI part
            doi_str = str(doi)
            if doi_str.startswith("https://doi.org/"):
                return doi_str[16:]  # Remove prefix
            elif doi_str.startswith("http://doi.org/"):
                return doi_str[15:]  # Remove prefix
            return doi_str
        return None

    def _get_pdf_url(self, work: dict[str, Any]) -> str | None:
        """Extract PDF URL from OpenAlex work."""
        open_access: Any = work.get("open_access", {})
        if isinstance(open_access, dict):
            oa_url = open_access.get("oa_url")
            if oa_url:
                return str(oa_url)
            # Also check if is_oa is True and use pdf_url if available
            is_oa = open_access.get("is_oa", False)
            if is_oa:
                # Try to get best OA location
                best_oa: Any = work.get("best_oa_location", {})
                if isinstance(best_oa, dict):
                    pdf_url = best_oa.get("pdf_url") or best_oa.get("landing_page_url")
                    if pdf_url:
                        return str(pdf_url)
        return None

    def _to_article(self, work: Any) -> Article:
        """Convert an OpenAlex work to an Article.

        Args:
            work: An OpenAlex Work object or dict.

        Returns:
            An Article model with unified fields.
        """
        # Handle both dict and object responses
        if isinstance(work, dict):
            return self._to_article_from_dict(work)

        # Convert object to dict for consistent processing
        work_dict: dict[str, Any] = dict(work)
        return self._to_article_from_dict(work_dict)

    def _to_article_from_dict(self, work: dict[str, Any]) -> Article:
        """Convert an OpenAlex work dict to an Article."""
        # Extract authors
        authors_raw: Any = work.get("authorships", [])
        authors: list[str] = []
        if isinstance(authors_raw, list):
            for authorship in authors_raw:
                if isinstance(authorship, dict):
                    author_data: Any = authorship.get("author", {})
                    if isinstance(author_data, dict):
                        name = author_data.get("display_name")
                    else:
                        name = getattr(author_data, "display_name", None)
                else:
                    name = getattr(authorship, "display_name", None)
                if name:
                    authors.append(str(name))

        # Handle DOI
        doi = self._get_doi(work)

        # Handle PDF URL
        pdf_url_str = self._get_pdf_url(work)
        pdf_url: HttpUrl | None = None
        if pdf_url_str:
            try:
                pdf_url = HttpUrl(pdf_url_str)
            except Exception:
                pdf_url = None

        # Handle URL (OpenAlex page)
        url_str: Any = work.get("id")
        url: HttpUrl | None = None
        if url_str:
            try:
                url = HttpUrl(str(url_str))
            except Exception:
                url = None

        # Handle year
        publication_date: Any = work.get("publication_date")
        year: int | None = None
        if publication_date:
            try:
                year = int(str(publication_date)[:4])
            except (ValueError, TypeError):
                year = None
        # Fallback to year field
        if year is None:
            year_raw: Any = work.get("publication_year")
            if year_raw is not None:
                try:
                    year = int(year_raw)
                except (ValueError, TypeError):
                    year = None

        # Handle journal/venue
        primary_location: Any = work.get("primary_location", {})
        source: Any = None
        if isinstance(primary_location, dict):
            source = primary_location.get("source", {})
        journal: str | None = None
        if isinstance(source, dict):
            journal = source.get("display_name")
        elif source is not None:
            journal = getattr(source, "display_name", None)

        # Handle publication type
        work_type: Any = work.get("type")
        publication_type: str = str(work_type) if work_type else "article"

        # Handle citation count
        cited_by_count: Any = work.get("cited_by_count")
        citation_count: int | None = None
        if cited_by_count is not None:
            try:
                citation_count = int(cited_by_count)
            except (ValueError, TypeError):
                citation_count = None

        # Handle open access
        open_access_data: Any = work.get("open_access", {})
        open_access: bool = False
        if isinstance(open_access_data, dict):
            open_access = bool(open_access_data.get("is_oa", False))

        # Handle biblio fields (volume, issue, pages)
        biblio: Any = work.get("biblio", {})
        volume: str | None = None
        issue: str | None = None
        pages: str | None = None
        if isinstance(biblio, dict):
            volume = biblio.get("volume")
            issue = biblio.get("issue")
            first_page = biblio.get("first_page")
            last_page = biblio.get("last_page")
            if first_page and last_page:
                pages = f"{first_page}-{last_page}"
            elif first_page:
                pages = str(first_page)

        return Article(
            source=self.SOURCE_NAME,
            external_id=str(work.get("id", "")).replace("https://openalex.org/", ""),
            title=str(work.get("display_name", "")),
            authors=authors,
            year=year,
            journal=journal,
            publication_type=publication_type,
            volume=volume,
            issue=issue,
            pages=pages,
            doi=doi,
            abstract=work.get("abstract"),
            url=url,
            pdf_url=pdf_url,
            open_access=open_access,
            citation_count=citation_count,
        )

    def _do_search(self, query: str, limit: int) -> list[Article]:
        """Internal search method (without timeout wrapper)."""
        works = Works().search(query).get(per_page=limit)

        articles: list[Article] = []
        for work in works:
            try:
                article = self._to_article(work)
                articles.append(article)
            except Exception:
                # Skip works that fail to parse
                continue

        return articles

    @timed
    def search(
        self,
        query: str,
        limit: int = 10,
        timeout: float = DEFAULT_SEARCH_TIMEOUT,
    ) -> list[Article]:
        """Search for papers on OpenAlex.

        Args:
            query: Search query string.
            limit: Maximum number of results to return.
            timeout: Maximum time to wait for results (default: 15s).

        Returns:
            List of Article objects. Empty list if timeout occurs.
        """
        try:
            return run_with_timeout(self._do_search, timeout, query, limit)
        except TimeoutError:
            logger.warning(
                f"OpenAlex search timed out after {timeout}s for query: {query[:50]}..."
            )
            return []

    def get_paper_by_doi(self, doi: str) -> Article | None:
        """Fetch a paper by its DOI.

        Args:
            doi: The DOI of the paper (with or without doi.org prefix).

        Returns:
            An Article if found, None otherwise.
        """
        try:
            # Normalize DOI
            if doi.startswith("https://doi.org/"):
                doi = doi[16:]
            elif doi.startswith("http://doi.org/"):
                doi = doi[15:]

            work: Any = Works()[f"doi:{doi}"]
            return self._to_article(work)
        except Exception:
            return None

    def get_paper_by_id(self, work_id: str) -> Article | None:
        """Fetch a paper by its OpenAlex ID.

        Args:
            work_id: The OpenAlex work ID (e.g., "W123456789").

        Returns:
            An Article if found, None otherwise.
        """
        try:
            # Normalize ID
            if not work_id.startswith("W") and not work_id.startswith("https://"):
                work_id = f"W{work_id}"

            work: Any = Works()[work_id]
            return self._to_article(work)
        except Exception:
            return None
