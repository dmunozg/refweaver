"""Unified search across multiple academic search engines."""

import os
import warnings
from typing import Any

from loguru import logger

from refweaver.adapters.openalex import OpenAlexAdapter
from refweaver.adapters.scholarly import GoogleScholarAdapter
from refweaver.adapters.semantic_scholar import SemanticScholarAdapter
from refweaver.dedup import deduplicate_articles
from refweaver.models import Article
from refweaver.timing import timed_info

DEFAULT_LIMIT_PER_SOURCE = 5


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


class UnifiedSearch:
    """Unified search across multiple academic databases.

    Provides a single interface to search Semantic Scholar, OpenAlex,
    and Google Scholar simultaneously with automatic deduplication.

    Note: Perplexity is NOT included here because it works differently -
    it takes full sentences/claims and performs semantic search, while
    these adapters require keyword-based queries. Use PerplexityAdapter
    directly for claim-based semantic search.
    """

    def __init__(
        self,
        semantic_scholar_api_key: str | None = None,
        openalex_email: str | None = None,
        use_scholarly_proxy: bool = False,
    ) -> None:
        """Initialize the unified search with all adapters.

        Args:
            semantic_scholar_api_key: Optional API key for Semantic Scholar
                                     (for higher rate limits).
            openalex_email: Email address for OpenAlex (recommended for
                           higher rate limits, can be any valid email).
            use_scholarly_proxy: Whether to use proxy rotation for Google
                                Scholar to help avoid rate limits.
        """
        self.semantic_scholar: SemanticScholarAdapter = SemanticScholarAdapter(
            api_key=semantic_scholar_api_key
        )
        self.openalex: OpenAlexAdapter = OpenAlexAdapter(api_key=openalex_email)
        self.google_scholar: GoogleScholarAdapter = GoogleScholarAdapter(
            use_proxy=use_scholarly_proxy
        )

        self._use_semantic_scholar_default = _env_flag(
            "REFWEAVER_USE_SEMANTIC_SCHOLAR",
            True,
        )
        self._use_openalex_default = _env_flag("REFWEAVER_USE_OPENALEX", True)
        self._use_google_scholar_default = _env_flag(
            "REFWEAVER_USE_GOOGLE_SCHOLAR",
            True,
        )

        logger.info("UnifiedSearch initialized with all adapters")

    @timed_info
    def search(
        self,
        query: str,
        limit: int | None = None,
        limit_per_source: int = DEFAULT_LIMIT_PER_SOURCE,
        use_semantic_scholar: bool | None = None,
        use_openalex: bool | None = None,
        use_google_scholar: bool | None = None,
        deduplicate: bool = True,
        title_threshold: float = 0.85,
        author_threshold: float = 0.5,
    ) -> list[Article]:
        """Search across multiple academic databases.

        Searches the specified sources and returns combined results.
        If any source fails (e.g., CAPTCHA, network error), it will be
        skipped and the search continues with remaining sources.

        Args:
            query: Search query string (keywords for keyword-based search).
            limit: Maximum total number of results to return (default: None = unlimited).
                   Applied AFTER deduplication.
            limit_per_source: Maximum results per source (default: 5).
                             Set lower/higher to balance coverage vs depth.
            use_semantic_scholar: Whether to search Semantic Scholar.
            use_openalex: Whether to search OpenAlex.
            use_google_scholar: Whether to search Google Scholar.
            deduplicate: Whether to deduplicate results (default: True).
            title_threshold: Minimum title similarity for deduplication
                           (0.0-1.0, default: 0.85).
            author_threshold: Minimum author overlap for deduplication
                            (0.0-1.0, default: 0.5).

        Returns:
            List of Article objects from all sources.

        Raises:
            UserWarning: If no articles are found from any source.

        Note:
            For semantic/claim-based search, use PerplexityAdapter directly.
            Defaults can be controlled by env vars: REFWEAVER_USE_SEMANTIC_SCHOLAR,
            REFWEAVER_USE_OPENALEX, REFWEAVER_USE_GOOGLE_SCHOLAR.
        """
        all_articles: list[Article] = []
        failed_sources: list[str] = []
        successful_sources: list[str] = []

        resolved_use_semantic_scholar = (
            self._use_semantic_scholar_default
            if use_semantic_scholar is None
            else use_semantic_scholar
        )
        resolved_use_openalex = self._use_openalex_default if use_openalex is None else use_openalex
        resolved_use_google_scholar = (
            self._use_google_scholar_default if use_google_scholar is None else use_google_scholar
        )

        sources: list[tuple[str, bool, Any]] = [
            (
                "Semantic Scholar",
                resolved_use_semantic_scholar,
                self.semantic_scholar,
            ),
            ("OpenAlex", resolved_use_openalex, self.openalex),
            ("Google Scholar", resolved_use_google_scholar, self.google_scholar),
        ]

        logger.info(
            f"Starting unified search for query: '{query}' "
            f"(limit={limit if limit else 'unlimited'}, per_source={limit_per_source})"
        )

        for source_name, enabled, adapter in sources:
            if not enabled:
                logger.debug(f"Skipping {source_name} (disabled)")
                continue

            try:
                logger.info(f"Searching {source_name}...")
                articles = adapter.search(query, limit=limit_per_source)

                if articles:
                    logger.info(f"{source_name} returned {len(articles)} articles")
                    all_articles.extend(articles)
                    successful_sources.append(source_name)
                else:
                    logger.warning(f"{source_name} returned 0 articles")

            except Exception as e:
                logger.error(f"{source_name} search failed: {e}")
                failed_sources.append(source_name)
                continue

        # Log summary
        if failed_sources:
            logger.warning(f"Failed sources: {', '.join(failed_sources)}")
        if successful_sources:
            logger.info(
                f"Successful sources: {', '.join(successful_sources)} "
                f"(total: {len(all_articles)} articles before deduplication)"
            )

        # Deduplicate if requested (before applying final limit)
        if deduplicate and all_articles:
            logger.info("Deduplicating results...")
            original_count = len(all_articles)
            all_articles = deduplicate_articles(
                all_articles,
                title_threshold=title_threshold,
                author_threshold=author_threshold,
            )
            deduped_count = len(all_articles)
            removed = original_count - deduped_count
            logger.info(f"Removed {removed} duplicate(s), {deduped_count} unique remaining")

        # Apply final limit AFTER deduplication (if specified)
        if limit is not None and len(all_articles) > limit:
            all_articles = all_articles[:limit]
            logger.info(f"Trimmed results to {limit} articles")

        # Raise warning if no results
        if not all_articles:
            warning_msg = (
                f"No articles found for query: '{query}'. "
                f"Successful sources: {successful_sources}. "
                f"Failed sources: {failed_sources}."
            )
            logger.warning(warning_msg)
            warnings.warn(warning_msg, UserWarning, stacklevel=2)

        logger.info(f"Search complete. Returning {len(all_articles)} articles")
        return all_articles

    def search_single_source(
        self,
        source: str,
        query: str,
        limit: int = 10,
    ) -> list[Article]:
        """Search a single source by name.

        Args:
            source: One of 'semantic_scholar', 'openalex', or 'google_scholar'.
            query: Search query string.
            limit: Maximum number of results.

        Returns:
            List of Article objects.

        Raises:
            ValueError: If source name is invalid.
            UserWarning: If no articles are found.
        """
        source_map: dict[str, tuple[Any, str]] = {
            "semantic_scholar": (self.semantic_scholar, "Semantic Scholar"),
            "openalex": (self.openalex, "OpenAlex"),
            "google_scholar": (self.google_scholar, "Google Scholar"),
        }

        if source not in source_map:
            raise ValueError(
                f"Invalid source: {source}. Must be one of: {', '.join(source_map.keys())}"
            )

        adapter, source_name = source_map[source]

        try:
            logger.info(f"Searching {source_name} for: '{query}'")
            articles: list[Article] = adapter.search(query, limit=limit)

            if not articles:
                warning_msg = f"No articles found from {source_name} for: '{query}'"
                logger.warning(warning_msg)
                warnings.warn(warning_msg, UserWarning, stacklevel=2)

            logger.info(f"Found {len(articles)} articles from {source_name}")
            return articles

        except Exception as e:
            logger.error(f"{source_name} search failed: {e}")
            warning_msg = f"Search failed for {source_name}: {e}"
            warnings.warn(warning_msg, UserWarning, stacklevel=2)
            return []
