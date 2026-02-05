"""Article enrichment utilities to fill missing metadata."""

from typing import Optional

from loguru import logger

from refweaver.adapters.openalex import OpenAlexAdapter
from refweaver.adapters.scholarly import GoogleScholarAdapter
from refweaver.adapters.semantic_scholar import SemanticScholarAdapter
from refweaver.models import Article


class ArticleEnricher:
    """Enrich articles with missing metadata using multiple strategies.

    Tries multiple approaches to fill gaps (especially abstracts):
    1. API detail endpoints (same source, fetch by ID)
    2. Cross-API lookup (other sources, by DOI)
    3. LLM-based web extraction (fetch URL, parse with local LLM)
    """

    def __init__(
        self,
        semantic_scholar_api_key: Optional[str] = None,
        openalex_email: Optional[str] = None,
        use_llm_extractor: bool = False,
        llm_model: Optional[str] = None,
    ) -> None:
        """Initialize the enricher with all adapters.

        Args:
            semantic_scholar_api_key: API key for Semantic Scholar.
            openalex_email: Email for OpenAlex (recommended).
            use_llm_extractor: Whether to enable LLM-based web extraction.
            llm_model: Local LLM model name/path for extraction (e.g., "Qwen3-30B").
        """
        self.semantic_scholar: SemanticScholarAdapter = SemanticScholarAdapter(
            api_key=semantic_scholar_api_key
        )
        self.openalex: OpenAlexAdapter = OpenAlexAdapter(api_key=openalex_email)
        self.google_scholar: GoogleScholarAdapter = GoogleScholarAdapter()

        self.use_llm_extractor = use_llm_extractor
        self.llm_model = llm_model

        if use_llm_extractor:
            logger.info(f"ArticleEnricher initialized with LLM extraction ({llm_model})")
        else:
            logger.info("ArticleEnricher initialized (API methods only)")

    def _fill_from_same_source(self, article: Article) -> Article:
        """Try to fill gaps by fetching detailed data from same source."""
        if article.abstract:
            return article

        logger.debug(f"Trying to fill abstract from {article.source}")

        try:
            if article.source == "semanticscholar" and article.external_id:
                detailed = self.semantic_scholar.get_paper_by_id(article.external_id)
                if detailed and detailed.abstract:
                    logger.info(f"Filled abstract from Semantic Scholar for: {article.title[:50]}...")
                    return article.model_copy(update={"abstract": detailed.abstract})

            elif article.source == "openalex" and article.external_id:
                detailed = self.openalex.get_paper_by_id(article.external_id)
                if detailed and detailed.abstract:
                    logger.info(f"Filled abstract from OpenAlex for: {article.title[:50]}...")
                    return article.model_copy(update={"abstract": detailed.abstract})

            # Google Scholar doesn't have a reliable get_by_id, skip

        except Exception as e:
            logger.warning(f"Failed to fill from {article.source}: {e}")

        return article

    def _fill_from_cross_api(self, article: Article) -> Article:
        """Try to fill gaps by querying other APIs via DOI."""
        if article.abstract or not article.doi:
            return article

        logger.debug(f"Trying cross-API lookup for DOI: {article.doi}")

        # Try each adapter in order of reliability for abstracts
        from typing import Any
        adapters: list[tuple[str, Any]] = [
            ("OpenAlex", self.openalex),
            ("Semantic Scholar", self.semantic_scholar),
        ]

        for source_name, adapter in adapters:
            # Skip if this is the same source we already tried
            if source_name.lower().replace(" ", "") == article.source:
                continue

            try:
                filled = adapter.get_paper_by_doi(article.doi)
                if filled and filled.abstract:
                    logger.info(
                        f"Filled abstract from {source_name} for: {article.title[:50]}..."
                    )
                    return article.model_copy(update={"abstract": filled.abstract})
            except Exception as e:
                logger.debug(f"{source_name} lookup failed: {e}")
                continue

        return article

    def _extract_with_llm(self, article: Article) -> Article:
        """Extract abstract by fetching URL and parsing with local LLM.

        This is a fallback method that fetches the article's landing page
        and uses a local LLM to extract the abstract text.
        """
        if article.abstract or not article.url or not self.use_llm_extractor:
            return article

        logger.debug(f"Attempting LLM extraction for: {article.title[:50]}...")

        try:
            # Fetch the page content
            import requests
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; RefWeaver/0.1; Academic research tool)"
            }
            response = requests.get(str(article.url), headers=headers, timeout=10)
            response.raise_for_status()

            # Parse HTML and extract text
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Get text content
            text = soup.get_text(separator="\n", strip=True)

            # Limit text length for LLM
            text = text[:8000]  # First 8K chars should contain abstract

            # Use LLM to extract abstract
            # TODO: Implement actual LLM call with pydantic-ai
            # For now, log that we would do this
            logger.info(
                f"LLM extraction ready for: {article.title[:50]}... "
                f"(text length: {len(text)} chars)"
            )

            # Placeholder - return unchanged
            # Actual implementation would use pydantic-ai here
            return article

        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return article

    def fill_abstract(
        self,
        article: Article,
        try_same_source: bool = True,
        try_cross_api: bool = True,
        try_llm: bool = False,
    ) -> Article:
        """Fill missing abstract using available methods.

        Args:
            article: Article to enrich.
            try_same_source: Try fetching detailed data from same source.
            try_cross_api: Try other APIs via DOI lookup.
            try_llm: Try LLM-based web extraction (requires use_llm_extractor=True).

        Returns:
            Article with filled abstract if found, otherwise original.
        """
        if article.abstract:
            return article

        original_source = article.source
        logger.info(f"Attempting to fill abstract for: {article.title[:50]}...")

        # Strategy 1: Same source detail endpoint
        if try_same_source:
            article = self._fill_from_same_source(article)
            if article.abstract:
                logger.success(f"Abstract filled from {original_source}")
                return article

        # Strategy 2: Cross-API lookup by DOI
        if try_cross_api:
            article = self._fill_from_cross_api(article)
            if article.abstract:
                logger.success(f"Abstract filled via cross-API lookup")
                return article

        # Strategy 3: LLM web extraction
        if try_llm and self.use_llm_extractor:
            article = self._extract_with_llm(article)
            if article.abstract:
                logger.success(f"Abstract filled via LLM extraction")
                return article

        logger.warning(f"Could not fill abstract for: {article.title[:50]}...")
        return article

    def fill_abstracts(
        self,
        articles: list[Article],
        try_same_source: bool = True,
        try_cross_api: bool = True,
        try_llm: bool = False,
    ) -> list[Article]:
        """Fill missing abstracts for a list of articles.

        Args:
            articles: List of articles to enrich.
            try_same_source: Try fetching detailed data from same source.
            try_cross_api: Try other APIs via DOI lookup.
            try_llm: Try LLM-based web extraction.

        Returns:
            List of articles with filled abstracts where possible.
        """
        logger.info(f"Filling abstracts for {len(articles)} articles...")

        filled_count = 0
        enriched_articles: list[Article] = []

        for article in articles:
            enriched = self.fill_abstract(
                article,
                try_same_source=try_same_source,
                try_cross_api=try_cross_api,
                try_llm=try_llm,
            )
            if enriched.abstract and not article.abstract:
                filled_count += 1
            enriched_articles.append(enriched)

        logger.info(f"Filled {filled_count}/{len(articles)} missing abstracts")
        return enriched_articles
