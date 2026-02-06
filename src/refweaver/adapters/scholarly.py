"""Google Scholar adapter for RefWeaver using scholarly library."""

from typing import Any

from pydantic import HttpUrl
from scholarly import ProxyGenerator, scholarly  # type: ignore[import-untyped]

from refweaver.models import Article


class GoogleScholarAdapter:
    """Adapter for Google Scholar using the scholarly library.

    Note: This uses web scraping and may be subject to rate limits
    and CAPTCHAs. For production use, consider using a proxy or
    falling back to other APIs.
    """

    SOURCE_NAME = "scholarly"

    def __init__(self, use_proxy: bool = False) -> None:
        """Initialize the Google Scholar adapter.

        Args:
            use_proxy: Whether to use a proxy generator to avoid
                      rate limiting. Requires free-proxy package.
        """
        if use_proxy:
            try:
                pg = ProxyGenerator()
                pg.FreeProxies()
                scholarly.use_proxy(pg)
            except Exception:
                # Proxy setup failed, continue without
                pass

    def _parse_authors(self, author_data: Any) -> list[str]:
        """Extract author names from scholarly author field.

        Authors can be a single string "Author1 and Author2 and Author3"
        or already a list.
        """
        if isinstance(author_data, list):
            return [str(a).strip() for a in author_data if a]

        if isinstance(author_data, str):
            # Authors often separated by " and "
            if " and " in author_data:
                return [a.strip() for a in author_data.split(" and ") if a.strip()]
            # Sometimes comma-separated
            if "," in author_data:
                return [a.strip() for a in author_data.split(",") if a.strip()]
            return [author_data.strip()] if author_data.strip() else []

        return []

    def _extract_year(self, year_data: Any) -> int | None:
        """Extract year from various formats."""
        if year_data is None:
            return None

        try:
            # Could be int or string
            year_str = str(year_data)
            # Extract first 4 digits that look like a year (1900-2099)
            import re
            match = re.search(r'\b(19|20)\d{2}\b', year_str)
            if match:
                return int(match.group(0))
            return int(year_str)
        except (ValueError, TypeError):
            return None

    def _to_article(self, publication: Any) -> Article:
        """Convert a scholarly publication to an Article.

        Args:
            publication: A scholarly publication dict or object.

        Returns:
            An Article model with unified fields.
        """
        # Handle both dict and object responses
        if isinstance(publication, dict):
            return self._to_article_from_dict(publication)

        # Convert object to dict
        pub_dict: dict[str, Any] = dict(publication)
        return self._to_article_from_dict(pub_dict)

    def _to_article_from_dict(self, publication: dict[str, Any]) -> Article:
        """Convert a scholarly publication dict to an Article."""
        # Get the bib (bibliography) data
        bib: dict[str, Any] = publication.get("bib", {})

        # Extract authors
        authors = self._parse_authors(bib.get("author"))

        # Extract year
        year = self._extract_year(bib.get("pub_year") or bib.get("year"))

        # Extract venue/journal
        journal = bib.get("venue") or bib.get("journal")

        # Get publication type (scholarly doesn't provide this directly)
        publication_type = "article"

        # Get abstract (may need to be filled)
        abstract = bib.get("abstract")

        # Get DOI if available
        doi = bib.get("doi")

        # Get URLs
        url_str: Any = publication.get("pub_url") or bib.get("url")
        url: HttpUrl | None = None
        if url_str:
            try:
                url = HttpUrl(str(url_str))
            except Exception:
                url = None

        # Try to get PDF URL
        pdf_url_str: Any = publication.get("eprint_url") or publication.get("pdf_url")
        pdf_url: HttpUrl | None = None
        if pdf_url_str:
            try:
                pdf_url = HttpUrl(str(pdf_url_str))
            except Exception:
                pdf_url = None

        # Determine if open access (heuristic)
        open_access = bool(pdf_url)

        # Get citation count
        citation_count: int | None = None
        if "num_citations" in publication:
            try:
                citation_count = int(publication["num_citations"])
            except (ValueError, TypeError):
                citation_count = None

        # Build external ID from Google Scholar ID
        gs_id = publication.get("gs_id") or publication.get("author_pub_id")
        external_id = str(gs_id) if gs_id else ""

        return Article(
            source=self.SOURCE_NAME,
            external_id=external_id,
            title=str(bib.get("title", "")),
            authors=authors,
            year=year,
            journal=journal,
            publication_type=publication_type,
            volume=bib.get("volume"),
            issue=bib.get("number"),  # scholarly uses 'number' for issue
            pages=bib.get("pages"),
            doi=doi,
            abstract=abstract,
            url=url,
            pdf_url=pdf_url,
            open_access=open_access,
            citation_count=citation_count,
        )

    def search(
        self,
        query: str,
        limit: int = 10,
        fill: bool = False,
    ) -> list[Article]:
        """Search for papers on Google Scholar.

        Args:
            query: Search query string.
            limit: Maximum number of results to return.
            fill: Whether to fill publication details (slower, more
                  complete data, but more likely to trigger CAPTCHA).

        Returns:
            List of Article objects.
        """
        articles: list[Article] = []

        try:
            # Get search results
            search_results = scholarly.search_pubs(query)

            for i, publication in enumerate(search_results):
                if i >= limit:
                    break

                try:
                    # Optionally fill in more details (slower)
                    if fill:
                        publication = scholarly.fill(publication)

                    article = self._to_article(publication)
                    articles.append(article)
                except Exception:
                    # Skip publications that fail to parse
                    continue

        except Exception:
            # Search failed (CAPTCHA, network, etc.)
            pass

        return articles

    def get_paper_by_doi(self, doi: str) -> Article | None:
        """Fetch a paper by its DOI.

        Note: Google Scholar doesn't have a direct DOI lookup,
        so we search for the DOI and return the first result.

        Args:
            doi: The DOI of the paper.

        Returns:
            An Article if found, None otherwise.
        """
        try:
            # Normalize DOI
            if doi.startswith("https://doi.org/"):
                doi = doi[16:]
            elif doi.startswith("http://doi.org/"):
                doi = doi[15:]

            # Search for the DOI
            search_results = scholarly.search_pubs(doi)

            for publication in search_results:
                try:
                    article = self._to_article(publication)
                    # Verify this is the right paper
                    if article.doi and article.doi.lower() == doi.lower():
                        return article
                    # Or check if title matches DOI search reasonably
                    if doi.lower() in str(publication.get("bib", {}).get("title", "")).lower():
                        return article
                except Exception:
                    continue

            return None
        except Exception:
            return None

    def get_paper_by_id(self, pub_id: str) -> Article | None:
        """Fetch a paper by its Google Scholar publication ID.

        Args:
            pub_id: The Google Scholar publication ID.

        Returns:
            An Article if found, None otherwise.
        """
        try:
            # Google Scholar IDs are tricky - we search and match
            # This is a best-effort approach
            search_results = scholarly.search_pubs(pub_id)

            for publication in search_results:
                try:
                    # Check if this publication matches the ID
                    if publication.get("gs_id") == pub_id:
                        return self._to_article(publication)
                    if publication.get("author_pub_id") == pub_id:
                        return self._to_article(publication)
                except Exception:
                    continue

            return None
        except Exception:
            return None
