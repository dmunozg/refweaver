"""Unified search with Perplexity fallback for RefWeaver.

This module extends the base UnifiedSearch to include Perplexity
as a fallback tier when primary academic sources return few results.
"""

import os
import warnings
from typing import Any

from loguru import logger

from refweaver.adapters.openalex import OpenAlexAdapter
from refweaver.adapters.perplexity import PerplexityAdapter
from refweaver.adapters.scholarly import GoogleScholarAdapter
from refweaver.adapters.semantic_scholar import SemanticScholarAdapter
from refweaver.dedup import deduplicate_articles
from refweaver.models import Article


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


class UnifiedSearchWithFallback:
    """Unified search with Perplexity fallback tier.

    Searches traditional academic databases first (Semantic Scholar,
    OpenAlex, Google Scholar). If results are below a threshold,
    automatically falls back to Perplexity Sonar for additional results.
    """

    def __init__(
        self,
        semantic_scholar_api_key: str | None = None,
        openalex_email: str | None = None,
        use_scholarly_proxy: bool = False,
        openrouter_api_key: str | None = None,
        perplexity_model: str = "perplexity/sonar",
        perplexity_fallback_threshold: int = 3,
    ) -> None:
        """Initialize the unified search with all adapters.

        Args:
            semantic_scholar_api_key: Optional API key for Semantic Scholar.
            openalex_email: Email address for OpenAlex (recommended).
            use_scholarly_proxy: Whether to use proxy rotation for Google Scholar.
            openrouter_api_key: OpenRouter API key for Perplexity fallback.
                               If not provided, will look for OPENROUTER_API_KEY env var.
            perplexity_model: Perplexity model to use for fallback.
                             Options: "perplexity/sonar", "perplexity/sonar-pro"
            perplexity_fallback_threshold: Minimum results from primary sources
                                          before triggering Perplexity fallback.
        """
        # Primary adapters
        self.semantic_scholar = SemanticScholarAdapter(api_key=semantic_scholar_api_key)
        self.openalex = OpenAlexAdapter(api_key=openalex_email)
        self.google_scholar = GoogleScholarAdapter(use_proxy=use_scholarly_proxy)

        # Fallback adapter (initialized lazily if needed)
        self._perplexity: PerplexityAdapter | None = None
        self._openrouter_api_key = openrouter_api_key
        self._perplexity_model = perplexity_model
        self.perplexity_fallback_threshold = perplexity_fallback_threshold

        self._use_semantic_scholar_default = _env_flag(
            "REFWEAVER_USE_SEMANTIC_SCHOLAR",
            True,
        )
        self._use_openalex_default = _env_flag("REFWEAVER_USE_OPENALEX", True)
        self._use_google_scholar_default = _env_flag(
            "REFWEAVER_USE_GOOGLE_SCHOLAR",
            True,
        )
        self._use_perplexity_default = _env_flag(
            "REFWEAVER_USE_PERPLEXITY",
            True,
        )

        logger.info(
            f"UnifiedSearchWithFallback initialized "
            f"(fallback_threshold={perplexity_fallback_threshold})"
        )

    def _get_perplexity_adapter(self) -> PerplexityAdapter:
        """Lazy initialization of Perplexity adapter."""
        if self._perplexity is None:
            self._perplexity = PerplexityAdapter(
                api_key=self._openrouter_api_key,
                model=self._perplexity_model,
            )
        return self._perplexity

    def search(
        self,
        query: str,
        limit: int = 10,
        limit_per_source: int | None = None,
        use_semantic_scholar: bool | None = None,
        use_openalex: bool | None = None,
        use_google_scholar: bool | None = None,
        use_perplexity_fallback: bool | None = None,
        deduplicate: bool = True,
        title_threshold: float = 0.85,
        author_threshold: float = 0.5,
    ) -> list[Article]:
        """Search across multiple academic databases with Perplexity fallback.

        Args:
            query: Search query string.
            limit: Maximum total number of results to return.
            limit_per_source: Maximum results per source (default: limit).
            use_semantic_scholar: Whether to search Semantic Scholar.
            use_openalex: Whether to search OpenAlex.
            use_google_scholar: Whether to search Google Scholar.
            use_perplexity_fallback: Whether to use Perplexity as fallback.
            deduplicate: Whether to deduplicate results.
            title_threshold: Minimum title similarity for deduplication.
            author_threshold: Minimum author overlap for deduplication.

        Returns:
            List of Article objects from all sources.

        Note:
            Defaults can be controlled by env vars: REFWEAVER_USE_SEMANTIC_SCHOLAR,
            REFWEAVER_USE_OPENALEX, REFWEAVER_USE_GOOGLE_SCHOLAR, REFWEAVER_USE_PERPLEXITY.
        """
        if limit_per_source is None:
            limit_per_source = limit

        all_articles: list[Article] = []
        failed_sources: list[str] = []
        successful_sources: list[str] = []

        # Phase 1: Search primary sources
        resolved_use_semantic_scholar = (
            self._use_semantic_scholar_default
            if use_semantic_scholar is None
            else use_semantic_scholar
        )
        resolved_use_openalex = self._use_openalex_default if use_openalex is None else use_openalex
        resolved_use_google_scholar = (
            self._use_google_scholar_default if use_google_scholar is None else use_google_scholar
        )
        resolved_use_perplexity = (
            self._use_perplexity_default
            if use_perplexity_fallback is None
            else use_perplexity_fallback
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
            f"Starting unified search for query: '{query[:50]}...' "
            f"(limit={limit}, per_source={limit_per_source})"
        )

        for source_name, enabled, adapter in sources:
            if not enabled:
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

        # Phase 2: Perplexity fallback if needed
        primary_count = len(all_articles)
        if resolved_use_perplexity and primary_count < self.perplexity_fallback_threshold:
            logger.info(
                f"Primary sources returned only {primary_count} articles "
                f"(threshold: {self.perplexity_fallback_threshold}), "
                f"triggering Perplexity fallback..."
            )

            try:
                perplexity = self._get_perplexity_adapter()
                # Request more from Perplexity since these need enrichment
                perplexity_limit = max(limit_per_source, 10)
                perplexity_articles = perplexity.search(query, limit=perplexity_limit)

                if perplexity_articles:
                    logger.info(f"Perplexity returned {len(perplexity_articles)} articles")
                    all_articles.extend(perplexity_articles)
                    successful_sources.append("Perplexity (fallback)")
                else:
                    logger.warning("Perplexity fallback returned 0 articles")

            except Exception as e:
                logger.error(f"Perplexity fallback failed: {e}")
                failed_sources.append("Perplexity (fallback)")

        # Deduplicate if requested
        if deduplicate and all_articles:
            logger.info("Deduplicating results...")
            original_count = len(all_articles)
            all_articles = deduplicate_articles(
                all_articles,
                title_threshold=title_threshold,
                author_threshold=author_threshold,
            )
            removed = original_count - len(all_articles)
            logger.info(f"Removed {removed} duplicate(s), {len(all_articles)} unique remaining")

        # Apply final limit
        if len(all_articles) > limit:
            all_articles = all_articles[:limit]
            logger.info(f"Trimmed results to {limit} articles")

        # Log summary
        if failed_sources:
            logger.warning(f"Failed sources: {', '.join(failed_sources)}")
        if successful_sources:
            logger.info(
                f"Successful sources: {', '.join(successful_sources)} | "
                f"Total: {len(all_articles)} articles"
            )

        # Warn if no results
        if not all_articles:
            warning_msg = f"No articles found for query: '{query}'"
            logger.warning(warning_msg)
            warnings.warn(warning_msg, UserWarning, stacklevel=2)

        return all_articles

    def search_with_enrichment(
        self,
        query: str,
        limit: int = 10,
        enrich_perplexity_results: bool = True,
        **search_kwargs: Any,
    ) -> list[Article]:
        """Search with automatic enrichment of Perplexity results.

        Since Perplexity returns URLs rather than full metadata, this method
        can optionally enrich those results using Crossref or Semantic Scholar.

        Args:
            query: Search query string.
            limit: Maximum total number of results.
            enrich_perplexity_results: Whether to enrich Perplexity results
                                      with additional metadata lookups.
            **search_kwargs: Additional arguments passed to search().

        Returns:
            List of enriched Article objects.
        """
        from refweaver.enrich import ArticleEnricher

        articles = self.search(query, limit=limit, **search_kwargs)

        if not enrich_perplexity_results:
            return articles

        # Enrich Perplexity results
        enricher = ArticleEnricher()
        enriched_articles: list[Article] = []

        for article in articles:
            if article.source == "perplexity":
                logger.debug(f"Enriching Perplexity result: {article.title}")
                enriched = enricher.fill_abstract(article)
                enriched_articles.append(enriched)
            else:
                enriched_articles.append(article)

        return enriched_articles
