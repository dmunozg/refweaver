"""Article enrichment utilities to fill missing metadata."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from loguru import logger

from refweaver.adapters.openalex import OpenAlexAdapter
from refweaver.adapters.scholarly import GoogleScholarAdapter
from refweaver.adapters.semantic_scholar import SemanticScholarAdapter
from refweaver.llm import LLMClient, LLMConfig
from refweaver.models import Article
from refweaver.rate_limit import rate_limit_url


class ArticleEnricher:
    """Enrich articles with missing metadata using multiple strategies.

    Tries multiple approaches to fill gaps (especially abstracts):
    1. API detail endpoints (same source, fetch by ID)
    2. Cross-API lookup (other sources, by DOI)
    3. LLM-based web extraction (fetch URL, parse with local LLM)
    """

    def __init__(
        self,
        semantic_scholar_api_key: str | None = None,
        openalex_email: str | None = None,
        use_llm_extractor: bool = True,
        llm_config: LLMConfig | None = None,
    ) -> None:
        """Initialize the enricher with all adapters.

        Args:
            semantic_scholar_api_key: API key for Semantic Scholar.
            openalex_email: Email for OpenAlex (recommended).
            use_llm_extractor: Whether to enable LLM-based web extraction.
            llm_config: LLM configuration. If None, uses environment defaults.
        """
        self.semantic_scholar: SemanticScholarAdapter = SemanticScholarAdapter(
            api_key=semantic_scholar_api_key
        )
        self.openalex: OpenAlexAdapter = OpenAlexAdapter(api_key=openalex_email)
        self.google_scholar: GoogleScholarAdapter = GoogleScholarAdapter()

        self.use_llm_extractor = use_llm_extractor
        self.llm_client: LLMClient | None = None

        if use_llm_extractor:
            self.llm_client = LLMClient(config=llm_config)
            logger.info(
                f"ArticleEnricher initialized with LLM extraction ({self.llm_client._model_name})"
            )
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
                    logger.info(
                        f"Filled abstract from Semantic Scholar for: {article.title[:50]}..."
                    )
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
                    logger.info(f"Filled abstract from {source_name} for: {article.title[:50]}...")
                    return article.model_copy(update={"abstract": filled.abstract})
            except Exception as e:
                logger.debug(f"{source_name} lookup failed: {e}")
                continue

        return article

    def _fetch_html_requests(self, url: str) -> str:
        """Fetch HTML using requests with browser-like headers.

        Args:
            url: URL to fetch.

        Returns:
            HTML content from the page.

        Raises:
            requests.HTTPError: If request fails (including 403).
        """
        import requests

        # Enhanced headers to look more like a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }

        rate_limit_url(url)
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        return response.text

    def _fetch_html_selenium(self, url: str) -> str:
        """Fetch HTML using Selenium as fallback for blocked sites.

        Args:
            url: URL to fetch.

        Returns:
            HTML content from the page.

        Raises:
            Exception: If Selenium fails to fetch the page.
        """
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        logger.debug(f"Using Selenium to fetch: {url}")

        # Configure Chrome options for headless browsing
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            rate_limit_url(url)
            driver.get(url)

            # Wait for page to load (wait for body element)
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Get page source
            html = driver.page_source
            logger.debug(f"Selenium successfully fetched page: {len(html)} chars")
            return html

        finally:
            if driver:
                driver.quit()

    def _fetch_html(self, url: str) -> str:
        """Fetch and clean HTML from a URL using Selenium.

        Uses Selenium directly since many publisher sites require JavaScript
        to render content properly. Plain requests often returns incomplete
        pages due to JavaScript-based content loading.

        Args:
            url: URL to fetch.

        Returns:
            Cleaned text content from the page.

        Raises:
            Exception: If Selenium fails to fetch the page.
        """
        from bs4 import BeautifulSoup

        logger.debug(f"Fetching with Selenium: {url}")

        # Use Selenium directly - many sites need JavaScript
        try:
            html = self._fetch_html_selenium(url)
            logger.debug(f"Selenium fetched: {len(html)} chars")
        except Exception as e:
            logger.error(f"Selenium failed to fetch {url}: {e}")
            raise

        # Parse HTML and extract text
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Get text content
        text = soup.get_text(separator="\n", strip=True)

        return text

    def _extract_with_llm(self, article: Article) -> Article:
        """Extract abstract and DOI by fetching URLs and parsing with local LLM.

        This is a fallback method that fetches both the article's landing page
        and the DOI-resolved page (if available), then uses a local LLM to
        extract the abstract text and DOI from the webpage content.

        The DOI is extracted separately from the abstract to avoid confusing
        the article's own DOI with DOIs found in the references section.
        The DOI is only set if the article doesn't already have one (to avoid
        overwriting known-good DOIs with potentially hallucinated ones).

        Args:
            article: Article to enrich.

        Returns:
            Article with extracted abstract and/or DOI if successful, otherwise original.
        """
        if article.abstract and article.doi:
            return article

        if not self.use_llm_extractor:
            return article

        # Need at least one URL to fetch
        if not article.url and not article.doi:
            return article

        logger.debug(f"Attempting LLM extraction for: {article.title[:50]}...")

        html_sources: list[str] = []

        try:
            # Strategy 1: Try DOI URL first (usually redirects to publisher page with abstract)
            if article.doi:
                doi_url = f"https://doi.org/{article.doi}"
                try:
                    logger.debug(f"Fetching DOI URL: {doi_url}")
                    doi_text = self._fetch_html(doi_url)
                    if doi_text:
                        html_sources.append(f"=== FROM DOI URL ({doi_url}) ===\n{doi_text[:8000]}")
                        logger.debug(f"DOI URL fetched, text length: {len(doi_text)}")
                except Exception as e:
                    logger.debug(f"DOI URL fetch failed: {e}")

            # Strategy 2: Try article URL as fallback (might be OpenAlex/Semantic Scholar page)
            if article.url:
                try:
                    url_str = str(article.url)
                    logger.debug(f"Fetching article URL: {url_str}")
                    url_text = self._fetch_html(url_str)
                    if url_text:
                        html_sources.append(
                            f"=== FROM ARTICLE URL ({url_str}) ===\n{url_text[:8000]}"
                        )
                        logger.debug(f"Article URL fetched, text length: {len(url_text)}")
                except Exception as e:
                    logger.debug(f"Article URL fetch failed: {e}")

            if not html_sources:
                logger.warning(f"No HTML content could be fetched for: {article.title[:50]}...")
                return article

            # Combine sources for LLM processing
            combined_text = "\n\n".join(html_sources)

            logger.info(
                f"LLM extraction ready for: {article.title[:50]}... "
                f"(sources: {len(html_sources)}, total length: {len(combined_text)} chars)"
            )

            # Use LLM to extract both abstract and DOI
            if self.llm_client is None:
                logger.error("LLM client not initialized")
                return article

            extracted = self.llm_client.extract_metadata_from_html(
                html_content=combined_text,
                article_title=article.title,
            )

            updates: dict[str, Any] = {}

            # Set abstract if found and article doesn't have one
            if extracted["abstract"] and not article.abstract:
                logger.success(f"LLM extracted abstract ({len(extracted['abstract'])} chars)")
                updates["abstract"] = extracted["abstract"]

            # Only set DOI if article doesn't already have one (avoid overwriting known-good DOI)
            if extracted["doi"] and not article.doi:
                logger.success(f"LLM extracted DOI: {extracted['doi']}")
                updates["doi"] = extracted["doi"]
            elif extracted["doi"] and article.doi:
                logger.debug(
                    f"LLM found DOI {extracted['doi']} but article already has DOI {article.doi}, "
                    f"keeping existing DOI"
                )

            if updates:
                return article.model_copy(update=updates)

            logger.warning(f"LLM could not extract abstract or DOI for: {article.title[:50]}...")
            return article

        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return article

    def enrich_from_crossref(self, article: Article) -> Article:
        """Enrich article metadata from CrossRef API using DOI.

        Queries CrossRef API with the article's DOI and updates
        all available fields with BibTeX-formatted metadata.

        Args:
            article: Article to enrich.

        Returns:
            Article with enriched metadata if successful, otherwise original.
        """
        if not article.doi:
            logger.debug(f"No DOI for article, skipping CrossRef: {article.title[:50]}...")
            return article

        logger.info(f"Enriching from CrossRef: {article.doi}")
        enriched = article.enrich_from_crossref()

        if enriched != article:
            logger.success(f"CrossRef enrichment successful for: {article.title[:50]}...")
        else:
            logger.debug(f"CrossRef enrichment failed or no new data for: {article.title[:50]}...")

        return enriched

    def enrich_from_pdf_doi(
        self,
        article: Article,
        similarity_threshold: float = 0.50,
        try_alternative_sources: bool = True,
    ) -> Article:
        """Enrich article by extracting DOI from PDF and validating with CrossRef.

        This strategy is useful when:
        - Title search returns truncated results that don't match well
        - The article URL or pdf_url points to a downloadable PDF
        - We need to discover the DOI from the PDF content itself

        Procedure:
        1. Check if article has a PDF URL
        2. Download and parse PDF for DOI patterns
        3. Query CrossRef with found DOI
        4. Validate: compare original title with CrossRef title
        5. If similarity >= threshold, merge metadata

        Args:
            article: Article to enrich (should have url or pdf_url).
            similarity_threshold: Minimum title similarity (0.0-1.0) to accept
                                 a CrossRef match. Default 0.50 (50%).
            try_alternative_sources: Whether to try finding PDF via Unpaywall
                                     if article doesn't have direct PDF URL.

        Returns:
            Article with enriched metadata if DOI found and validated,
            otherwise returns original article.
        """
        from refweaver.dedup import merge_articles, title_similarity
        from refweaver.pdf_extract import (
            extract_doi_from_pdf_url,
            is_pdf_url,
        )

        # Skip if we already have a DOI
        if article.doi:
            logger.debug(f"Article already has DOI, skipping PDF extraction: {article.doi}")
            return article

        if not article.title or len(article.title) < 5:
            logger.debug("Article has no usable title, cannot validate PDF-extracted DOI")
            return article

        # Determine PDF URL to try
        pdf_url: str | None = None

        # First: check if pdf_url is available and points to PDF
        if article.pdf_url:
            url_str = str(article.pdf_url)
            if is_pdf_url(url_str) or article.open_access:
                pdf_url = url_str
                logger.debug(f"Using article pdf_url: {pdf_url}")

        # Second: check if main url is a PDF
        if not pdf_url and article.url:
            url_str = str(article.url)
            if is_pdf_url(url_str):
                pdf_url = url_str
                logger.debug(f"Using article url (detected as PDF): {pdf_url}")

        # Third: try to find PDF via alternative sources
        if not pdf_url and try_alternative_sources:
            from refweaver.pdf_sources import find_pdf_url

            logger.debug("Searching for PDF via alternative sources...")
            alt_url = find_pdf_url(article, email=None)
            if alt_url:
                pdf_url = alt_url
                logger.debug(f"Found PDF via alternative source: {pdf_url}")

        if not pdf_url:
            logger.debug(f"No PDF URL available for: {article.title[:50]}...")
            return article

        logger.info(f"Attempting DOI extraction from PDF: {article.title[:50]}...")

        # Extract DOI from PDF
        extracted_doi = extract_doi_from_pdf_url(pdf_url, timeout=60)

        if not extracted_doi:
            logger.debug(f"No DOI found in PDF for: {article.title[:50]}...")
            return article

        logger.info(f"Found DOI in PDF: {extracted_doi}")

        # Create a temporary article with the extracted DOI to query CrossRef
        from datetime import date

        temp_article = Article(
            source="pdf_extraction",
            external_id=extracted_doi,
            title=article.title,  # Keep original title for comparison
            authors=article.authors,
            doi=extracted_doi,
            retrieved_at=date.today(),
        )

        # Query CrossRef for metadata
        logger.info(f"Validating extracted DOI with CrossRef: {extracted_doi}")
        crossref_article = temp_article.enrich_from_crossref()

        # Check if CrossRef returned useful data
        if crossref_article == temp_article or not crossref_article.title:
            logger.warning(f"CrossRef returned no metadata for DOI: {extracted_doi}")
            return article

        # Validate: compare titles
        crossref_title = crossref_article.title
        original_title = article.title

        similarity = title_similarity(original_title, crossref_title)
        logger.info(
            f"Title similarity: {similarity:.2%} "
            f"(original: '{original_title[:50]}...' vs "
            f"crossref: '{crossref_title[:50]}...')"
        )

        if similarity < similarity_threshold:
            logger.warning(
                f"Title similarity ({similarity:.2%}) below threshold "
                f"({similarity_threshold:.2%}). DOI likely incorrect: {extracted_doi}"
            )
            return article

        logger.success(f"DOI validated ({similarity:.2%} match). Enriching with CrossRef metadata.")

        # Merge the CrossRef metadata into the original article
        merged = merge_articles([article, crossref_article])

        if merged:
            logger.info(
                f"Successfully enriched from PDF DOI: "
                f"DOI={merged.doi}, authors={len(merged.authors)}, year={merged.year}"
            )
            return merged

        return article

    def find_doi(
        self,
        article: Article,
        try_title_search: bool = True,
        try_pdf_extraction: bool = True,
        try_llm_extraction: bool = True,
        title_similarity_threshold: float = 0.85,
        pdf_similarity_threshold: float = 0.50,
    ) -> Article:
        """Find DOI for an article using multiple strategies in order of cost.

        This method attempts to discover the DOI for an article that doesn't have one,
        trying strategies from least to most computationally expensive:

        1. Trivial check: Already has DOI (return immediately)
        2. Title search: Query OpenAlex API by title (fast API call)
        3. PDF extraction: Download PDF, parse for DOI pattern (network + I/O)
        4. LLM extraction: Fetch webpage, use LLM to extract DOI (network + LLM inference)

        The method stops as soon as a DOI is found and validated.

        Args:
            article: Article to find DOI for.
            try_title_search: Whether to try searching by title in OpenAlex.
            try_pdf_extraction: Whether to try extracting DOI from PDF.
            try_llm_extraction: Whether to try extracting DOI using LLM.
            title_similarity_threshold: Min similarity for title search matches.
            pdf_similarity_threshold: Min similarity for PDF-extracted DOI validation.

        Returns:
            Article with DOI if found, otherwise original article.
        """
        from refweaver.dedup import title_similarity

        # Strategy 0: Trivial check - already has DOI
        if article.doi:
            logger.debug(f"Article already has DOI: {article.doi}")
            return article

        if not article.title or len(article.title) < 5:
            logger.warning(f"Article has no usable title, cannot find DOI: {article.title[:50]}...")
            return article

        logger.info(f"Attempting to find DOI for: {article.title[:50]}...")

        # Strategy 1: Title search via OpenAlex (fast API call)
        if try_title_search:
            logger.debug("Strategy 1: Searching OpenAlex by title...")
            try:
                clean_title = article.title.rstrip(".").rstrip()
                results = self.openalex.search(clean_title, limit=5)

                for candidate in results:
                    if not candidate.title or not candidate.doi:
                        continue

                    sim = title_similarity(clean_title, candidate.title.rstrip(".").rstrip())
                    logger.debug(f"Title match similarity: {sim:.3f}")

                    if sim >= title_similarity_threshold:
                        logger.success(
                            f"Found DOI via title search: {candidate.doi} (similarity: {sim:.2%})"
                        )
                        return article.model_copy(update={"doi": candidate.doi})

                logger.debug("No suitable match found via title search")

            except Exception as e:
                logger.warning(f"Title search failed: {e}")

        # Strategy 2: PDF extraction (network I/O, no LLM)
        if try_pdf_extraction:
            logger.debug("Strategy 2: Extracting DOI from PDF...")
            try:
                enriched = self.enrich_from_pdf_doi(
                    article,
                    similarity_threshold=pdf_similarity_threshold,
                    try_alternative_sources=True,
                )
                if enriched.doi and not article.doi:
                    logger.success(f"Found DOI via PDF extraction: {enriched.doi}")
                    return enriched

                logger.debug("No DOI found in PDF")

            except Exception as e:
                logger.warning(f"PDF extraction failed: {e}")

        # Strategy 3: LLM extraction (most expensive - requires webpage fetch + LLM)
        if try_llm_extraction and self.use_llm_extractor and self.llm_client:
            logger.debug("Strategy 3: Extracting DOI using LLM...")
            try:
                # Need URLs to fetch
                if not article.url and not article.doi:
                    logger.debug("No URLs available for LLM extraction")
                else:
                    # Fetch HTML from available sources
                    html_sources: list[str] = []

                    if article.url:
                        try:
                            url_str = str(article.url)
                            logger.debug(f"Fetching article URL for LLM: {url_str}")
                            url_text = self._fetch_html(url_str)
                            if url_text:
                                html_sources.append(
                                    f"=== FROM ARTICLE URL ({url_str}) ===\n{url_text[:8000]}"
                                )
                        except Exception as e:
                            logger.debug(f"Article URL fetch failed: {e}")

                    if html_sources:
                        combined_text = "\n\n".join(html_sources)
                        logger.info(f"LLM DOI extraction ready: {len(combined_text)} chars")

                        extracted = self.llm_client.extract_metadata_from_html(
                            html_content=combined_text,
                            article_title=article.title,
                        )

                        if extracted.get("doi"):
                            doi = extracted["doi"]
                            logger.success(f"Found DOI via LLM extraction: {doi}")
                            return article.model_copy(update={"doi": doi})

                        logger.debug("LLM could not extract DOI from webpage")
                    else:
                        logger.debug("No HTML content could be fetched for LLM extraction")

            except Exception as e:
                logger.warning(f"LLM extraction failed: {e}")

        logger.warning(f"Could not find DOI for: {article.title[:50]}...")
        return article

    def enrich(
        self,
        article: Article,
        require_article_type: bool = True,
        doi_strategies: dict[str, bool] | None = None,
        abstract_strategies: dict[str, bool] | None = None,
    ) -> Article:
        """Fully enrich an article with DOI discovery and abstract filling.

        This is the high-level enrichment orchestrator that:
        1. Checks if the article should be enriched (must be entry_type="article" by default)
        2. Discovers the DOI using all available methods (title, PDF, LLM)
        3. Enriches metadata from CrossRef if DOI was found
        4. Fills the abstract using all available methods

        The method respects existing data - it won't overwrite a DOI or abstract
        that the article already has.

        Args:
            article: Article to enrich.
            require_article_type: If True (default), only enrich if entry_type is "article".
                                  Set to False to try enriching any entry type.
            doi_strategies: Optional dict to control DOI discovery strategies:
                - "title_search": Try OpenAlex title search (default: True)
                - "pdf_extraction": Try PDF DOI extraction (default: True)
                - "llm_extraction": Try LLM webpage extraction (default: True)
            abstract_strategies: Optional dict to control abstract filling strategies:
                - "same_source": Try same source detail endpoint (default: True)
                - "cross_api": Try cross-API lookup by DOI (default: True)
                - "crossref": Try CrossRef enrichment (default: True)
                - "title_search": Try OpenAlex title search (default: True)
                - "pdf_doi": Try PDF DOI extraction (default: True)
                - "llm": Try LLM web extraction (default: True)

        Returns:
            Fully enriched Article with DOI and abstract if found.
        """
        # Default strategy configurations
        default_doi_strategies = {
            "title_search": True,
            "pdf_extraction": True,
            "llm_extraction": True,
        }
        if doi_strategies:
            default_doi_strategies.update(doi_strategies)

        default_abstract_strategies = {
            "same_source": True,
            "cross_api": True,
            "crossref": True,
            "title_search": True,
            "pdf_doi": True,
            "llm": True,
        }
        if abstract_strategies:
            default_abstract_strategies.update(abstract_strategies)

        logger.info(f"Starting full enrichment for: {article.title[:50]}...")
        logger.debug(
            f"Initial state: DOI={article.doi is not None}, abstract={article.abstract is not None}"
        )

        # Step 1: Check entry type
        if require_article_type and article.entry_type.lower() != "article":
            logger.info(
                f"Skipping DOI discovery (entry_type='{article.entry_type}' != 'article'). "
                f"Proceeding to abstract filling only."
            )
            # Skip to abstract filling only
            return self.fill_abstract(
                article,
                try_same_source=default_abstract_strategies["same_source"],
                try_cross_api=default_abstract_strategies["cross_api"],
                try_crossref=default_abstract_strategies["crossref"],
                try_title_search=default_abstract_strategies["title_search"],
                try_pdf_doi=default_abstract_strategies["pdf_doi"],
                try_llm=default_abstract_strategies["llm"],
            )

        # Step 2: Find DOI (if not already present)
        if not article.doi:
            logger.debug("Step 2: Finding DOI...")
            article = self.find_doi(
                article,
                try_title_search=default_doi_strategies["title_search"],
                try_pdf_extraction=default_doi_strategies["pdf_extraction"],
                try_llm_extraction=default_doi_strategies["llm_extraction"],
            )

        # Step 3: Enrich from CrossRef if DOI was found
        if article.doi:
            logger.debug("Step 3: Enriching from CrossRef...")
            article = self.enrich_from_crossref(article)

        # Step 4: Fill abstract (if not already present)
        if not article.abstract:
            logger.debug("Step 4: Filling abstract...")
            article = self.fill_abstract(
                article,
                try_same_source=default_abstract_strategies["same_source"],
                try_cross_api=default_abstract_strategies["cross_api"],
                try_crossref=default_abstract_strategies["crossref"],
                try_title_search=default_abstract_strategies["title_search"],
                try_pdf_doi=default_abstract_strategies["pdf_doi"],
                try_llm=default_abstract_strategies["llm"],
            )

        # Log final state
        logger.success(
            f"Enrichment complete: DOI={article.doi is not None}, "
            f"abstract={article.abstract is not None} "
            f"({len(article.abstract) if article.abstract else 0} chars)"
        )

        return article

    def batch_enrich(
        self,
        articles: list[Article],
        require_article_type: bool = True,
        doi_strategies: dict[str, bool] | None = None,
        abstract_strategies: dict[str, bool] | None = None,
        max_workers: int | None = None,
    ) -> list[Article]:
        """Enrich a list of articles in parallel.

        Args:
            articles: List of articles to enrich.
            require_article_type: If True, only enrich entry_type="article" items.
            doi_strategies: Optional dict to control DOI discovery strategies.
            abstract_strategies: Optional dict to control abstract filling strategies.
            max_workers: Maximum parallel workers (defaults to REFWEAVER_ENRICH_MAX_WORKERS
                or 4 if not set).

        Returns:
            List of enriched articles in the original order.
        """
        if not articles:
            return []

        if max_workers is None:
            max_workers_env = os.getenv("REFWEAVER_ENRICH_MAX_WORKERS", "4")
            try:
                max_workers = max(1, int(max_workers_env))
            except ValueError:
                max_workers = 4

        logger.info(
            f"Starting parallel enrichment for {len(articles)} articles (max_workers={max_workers})"
        )

        results: list[Article | None] = [None] * len(articles)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self.enrich,
                    article,
                    require_article_type,
                    doi_strategies,
                    abstract_strategies,
                ): idx
                for idx, article in enumerate(articles)
            }

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.warning(f"Parallel enrichment failed for index {idx}: {e}")
                    results[idx] = articles[idx]

        enriched_articles = [article for article in results if article is not None]
        logger.info(
            f"Parallel enrichment complete: {len(enriched_articles)}/{len(articles)} results"
        )
        return enriched_articles

    def enrich_batch(
        self,
        articles: list[Article],
        require_article_type: bool = True,
        doi_strategies: dict[str, bool] | None = None,
        abstract_strategies: dict[str, bool] | None = None,
    ) -> list[Article]:
        """Fully enrich a list of articles.

        Args:
            articles: List of articles to enrich.
            require_article_type: If True, only enrich entry_type="article" items.
            doi_strategies: Optional dict to control DOI discovery strategies.
            abstract_strategies: Optional dict to control abstract filling strategies.

        Returns:
            List of enriched articles.
        """
        logger.info(f"Starting batch enrichment for {len(articles)} articles...")

        enriched_count = 0
        doi_found_count = 0
        abstract_filled_count = 0

        enriched_articles: list[Article] = []

        for i, article in enumerate(articles, 1):
            logger.info(f"Processing article {i}/{len(articles)}: {article.title[:50]}...")

            original_doi = article.doi
            original_abstract = article.abstract

            enriched = self.enrich(
                article,
                require_article_type=require_article_type,
                doi_strategies=doi_strategies,
                abstract_strategies=abstract_strategies,
            )

            # Track improvements
            if enriched != article:
                enriched_count += 1
            if enriched.doi and not original_doi:
                doi_found_count += 1
            if enriched.abstract and not original_abstract:
                abstract_filled_count += 1

            enriched_articles.append(enriched)

        logger.info(
            f"Batch enrichment complete: "
            f"{enriched_count}/{len(articles)} articles improved, "
            f"{doi_found_count} DOIs found, "
            f"{abstract_filled_count} abstracts filled"
        )

        return enriched_articles

    def enrich_from_title(
        self,
        article: Article,
        similarity_threshold: float = 0.85,
    ) -> Article:
        """Enrich article metadata by searching for the title in OpenAlex.

        Searches OpenAlex using the article's title, checks for a high-similarity
        match, and merges the found article's metadata (including DOI) into the
        original article.

        This is particularly useful for articles from sources like Perplexity
        that may have titles but lack DOIs and other metadata.

        Args:
            article: Article to enrich (must have a title).
            similarity_threshold: Minimum title similarity (0.0-1.0) to accept
                                 a match. Default 0.85 to handle truncated titles.

        Returns:
            Article with enriched metadata if match found, otherwise original.
        """
        if not article.title or len(article.title) < 10:
            logger.debug(
                f"Title too short or missing, skipping title enrichment: {article.title[:50]}..."
            )
            return article

        # Skip if we already have a DOI (use CrossRef instead)
        if article.doi:
            logger.debug(f"Article already has DOI, skipping title enrichment: {article.doi}")
            return article

        # Clean the title (remove trailing "..." from truncated titles)
        clean_title = article.title.rstrip(".").rstrip()

        logger.info(f"Searching OpenAlex by title: {clean_title[:60]}...")

        try:
            # Search OpenAlex with the title
            from refweaver.dedup import merge_articles, title_similarity

            results = self.openalex.search(clean_title, limit=5)

            if not results:
                logger.debug(f"No results from OpenAlex for title: {clean_title[:50]}...")
                return article

            # Find best match above threshold
            best_match: Article | None = None
            best_similarity = 0.0

            for candidate in results:
                if not candidate.title:
                    continue

                # Clean candidate title too
                clean_candidate = candidate.title.rstrip(".").rstrip()
                sim = title_similarity(clean_title, clean_candidate)
                logger.debug(f"Title similarity: {sim:.3f} - '{candidate.title[:60]}...'")

                if sim >= similarity_threshold and sim > best_similarity:
                    best_match = candidate
                    best_similarity = sim

            if best_match:
                logger.success(
                    f"Found match with similarity {best_similarity:.3f}: {best_match.title[:50]}..."
                )
                # Merge the matched article's metadata into the original
                merged = merge_articles([article, best_match])
                if merged:
                    logger.info(
                        f"Merged metadata: DOI={merged.doi is not None}, "
                        f"authors={len(merged.authors)}, year={merged.year}"
                    )
                    return merged
            else:
                logger.debug(
                    f"No match above threshold {similarity_threshold} for: {clean_title[:50]}..."
                )

        except Exception as e:
            logger.warning(f"Title enrichment failed: {e}")

        return article

    def fill_abstract(
        self,
        article: Article,
        try_same_source: bool = True,
        try_cross_api: bool = True,
        try_crossref: bool = True,
        try_title_search: bool = True,
        try_pdf_doi: bool = True,
        try_llm: bool = True,
    ) -> Article:
        """Fill missing abstract using available methods.

        Args:
            article: Article to enrich.
            try_same_source: Try fetching detailed data from same source.
            try_cross_api: Try other APIs via DOI lookup.
            try_crossref: Try CrossRef BibTeX enrichment.
            try_title_search: Try searching by title in OpenAlex.
            try_pdf_doi: Try extracting DOI from PDF and validating with CrossRef.
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
                logger.success("Abstract filled via cross-API lookup")
                return article

        # Strategy 3: CrossRef enrichment
        if try_crossref and article.doi:
            article = self.enrich_from_crossref(article)
            if article.abstract:
                logger.success("Abstract filled via CrossRef")
                return article

        # Strategy 4: Title-based search (for articles without DOI)
        if try_title_search and not article.doi:
            article = self.enrich_from_title(article)
            if article.abstract:
                logger.success("Abstract filled via title search")
                return article

        # Strategy 5: Extract DOI from PDF (useful when title search is truncated)
        if try_pdf_doi and not article.doi:
            article = self.enrich_from_pdf_doi(article)
            if article.abstract:
                logger.success("Abstract filled via PDF DOI extraction")
                return article
            # If we now have a DOI but no abstract, try crossref
            if article.doi and not article.abstract:
                article = self.enrich_from_crossref(article)
                if article.abstract:
                    logger.success("Abstract filled via PDF DOI + CrossRef")
                    return article

        # Strategy 6: LLM web extraction
        if try_llm and self.use_llm_extractor:
            article = self._extract_with_llm(article)
            if article.abstract:
                logger.success("Abstract filled via LLM extraction")
                return article

        logger.warning(f"Could not fill abstract for: {article.title[:50]}...")
        return article

    def fill_abstracts(
        self,
        articles: list[Article],
        try_same_source: bool = True,
        try_cross_api: bool = True,
        try_crossref: bool = True,
        try_title_search: bool = True,
        try_pdf_doi: bool = True,
        try_llm: bool = False,
    ) -> list[Article]:
        """Fill missing abstracts for a list of articles.

        Args:
            articles: List of articles to enrich.
            try_same_source: Try fetching detailed data from same source.
            try_cross_api: Try other APIs via DOI lookup.
            try_crossref: Try CrossRef BibTeX enrichment.
            try_title_search: Try searching by title in OpenAlex.
            try_pdf_doi: Try extracting DOI from PDF and validating with CrossRef.
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
                try_crossref=try_crossref,
                try_title_search=try_title_search,
                try_pdf_doi=try_pdf_doi,
                try_llm=try_llm,
            )
            if enriched.abstract and not article.abstract:
                filled_count += 1
            enriched_articles.append(enriched)

        logger.info(f"Filled {filled_count}/{len(articles)} missing abstracts")
        return enriched_articles
