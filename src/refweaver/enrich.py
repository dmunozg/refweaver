"""Article enrichment utilities to fill missing metadata."""

from typing import Optional

from loguru import logger

from refweaver.adapters.openalex import OpenAlexAdapter
from refweaver.adapters.scholarly import GoogleScholarAdapter
from refweaver.adapters.semantic_scholar import SemanticScholarAdapter
from refweaver.llm import LLMClient, LLMConfig
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
        llm_config: Optional[LLMConfig] = None,
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
        self.llm_client: Optional[LLMClient] = None

        if use_llm_extractor:
            self.llm_client = LLMClient(config=llm_config)
            logger.info(f"ArticleEnricher initialized with LLM extraction ({self.llm_client.model})")
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
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

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
        """Fetch and clean HTML from a URL with fallback to Selenium.

        First tries requests with browser headers, falls back to Selenium
        if we get a 403 Forbidden (bot detection).

        Args:
            url: URL to fetch.

        Returns:
            Cleaned text content from the page.

        Raises:
            Exception: If both requests and Selenium fail.
        """
        from bs4 import BeautifulSoup

        html = ""

        # Strategy 1: Try requests with enhanced headers
        try:
            logger.debug(f"Fetching with requests: {url}")
            html = self._fetch_html_requests(url)
            logger.debug(f"Requests succeeded: {len(html)} chars")
        except Exception as e:
            # Check if it's a 403 Forbidden
            is_403 = False
            if hasattr(e, "response") and e.response is not None:
                is_403 = getattr(e.response, "status_code", None) == 403

            if is_403:
                logger.warning(f"Got 403 from {url}, falling back to Selenium")
            else:
                logger.debug(f"Requests failed ({e}), trying Selenium")

            # Strategy 2: Fall back to Selenium
            try:
                html = self._fetch_html_selenium(url)
            except Exception as selenium_error:
                logger.error(f"Selenium also failed: {selenium_error}")
                raise Exception(f"Failed to fetch {url}: requests failed ({e}), Selenium failed ({selenium_error})")

        # Parse HTML and extract text
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Get text content
        text = soup.get_text(separator="\n", strip=True)

        return text

    def _extract_with_llm(self, article: Article) -> Article:
        """Extract abstract by fetching URLs and parsing with local LLM.

        This is a fallback method that fetches both the article's landing page
        and the DOI-resolved page (if available), then uses a local LLM to
        extract the abstract text from whichever source has more content.

        Args:
            article: Article to enrich.

        Returns:
            Article with extracted abstract if successful, otherwise original.
        """
        if article.abstract or not self.use_llm_extractor:
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
                        html_sources.append(f"=== FROM ARTICLE URL ({url_str}) ===\n{url_text[:8000]}")
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

            # Use LLM to extract abstract
            if self.llm_client is None:
                logger.error("LLM client not initialized")
                return article

            abstract = self.llm_client.extract_abstract_from_html(
                html_content=combined_text,
                article_title=article.title,
            )

            if abstract:
                logger.success(f"LLM extracted abstract ({len(abstract)} chars)")
                return article.model_copy(update={"abstract": abstract})

            logger.warning(f"LLM could not extract abstract for: {article.title[:50]}...")
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
