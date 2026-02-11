"""Perplexity Sonar adapter for RefWeaver via OpenRouter."""

import os
from datetime import date
from typing import Any

import requests
from loguru import logger
from pydantic import HttpUrl

from refweaver.models import Article
from refweaver.rate_limit import rate_limit
from refweaver.timing import run_with_timeout, timed

DEFAULT_SEARCH_TIMEOUT = 30.0  # seconds - Perplexity is slower due to LLM generation


class PerplexityAdapter:
    """Adapter for Perplexity Sonar API via OpenRouter.

    Uses Perplexity's Sonar models to search for academic papers
    and returns structured Article models. Acts as a fallback
    when traditional academic search engines return few results.
    """

    SOURCE_NAME = "perplexity"
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str | None = None, model: str = "perplexity/sonar") -> None:
        """Initialize the Perplexity adapter via OpenRouter.

        Args:
            api_key: OpenRouter API key. If not provided, will look for
                    OPENROUTER_API_KEY environment variable.
            model: Perplexity model to use. Options:
                   - "perplexity/sonar" (fast, cheap)
                   - "perplexity/sonar-pro" (better quality)
                   - "perplexity/sonar-reasoning" (complex reasoning)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. Provide api_key parameter "
                "or set OPENROUTER_API_KEY environment variable."
            )

        self.model = model
        self.base_url = self.OPENROUTER_BASE_URL
        logger.info(f"PerplexityAdapter initialized with model: {model}")

    def _make_request(
        self, messages: list[dict[str, str]], temperature: float = 0.2
    ) -> dict[str, Any]:
        """Make a request to OpenRouter API.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature (0.0 = deterministic).

        Returns:
            JSON response from the API.

        Raises:
            requests.RequestException: If the API request fails.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/dmunozg/refweaver",  # Required by OpenRouter
            "X-Title": "RefWeaver Academic Search",  # Helps with rate limits
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        rate_limit("perplexity")
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def _extract_annotations(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract structured citation annotations from Perplexity response.

        OpenRouter/Perplexity returns rich annotations with titles and URLs.

        Args:
            response: The API response dict.

        Returns:
            List of annotation dicts with 'url' and 'title' keys.
        """
        annotations: list[dict[str, Any]] = []

        choices_raw = response.get("choices", [])
        choices: list[Any] = choices_raw if isinstance(choices_raw, list) else []
        if choices:
            message_raw = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            message: dict[str, Any] = message_raw if isinstance(message_raw, dict) else {}
            msg_annotations_raw = message.get("annotations", [])
            msg_annotations: list[Any] = (
                msg_annotations_raw if isinstance(msg_annotations_raw, list) else []
            )
            for ann in msg_annotations:
                if isinstance(ann, dict) and ann.get("type") == "url_citation":
                    url_citation = ann.get("url_citation", {})
                    if url_citation:
                        annotations.append(
                            {
                                "url": url_citation.get("url", ""),
                                "title": url_citation.get("title", ""),
                            }
                        )

        return annotations

    def _extract_citation_urls(self, response: dict[str, Any]) -> list[str]:
        """Extract citation URLs from Perplexity response.

        Perplexity returns citations in the response metadata.

        Args:
            response: The API response dict.

        Returns:
            List of citation URLs.
        """
        citations: list[str] = []

        # Check response-level citations array
        response_citations = response.get("citations")
        if response_citations and isinstance(response_citations, list):
            citations.extend(str(c) for c in response_citations if isinstance(c, str))

        return list(set(citations))  # Deduplicate

    def _parse_article_from_url(
        self, url: str, title_override: str | None = None
    ) -> Article | None:
        """Create a minimal Article from a citation URL.

        This is a best-effort parsing since Perplexity returns URLs,
        not structured metadata. For better results, we should
        enrich these with Crossref or Semantic Scholar.

        Args:
            url: The citation URL (may be arXiv, DOI resolver, publisher site, etc.).

        Returns:
            Article if parsing succeeds, None otherwise.
        """
        try:
            parsed_url = HttpUrl(url)

            # Try to extract DOI from URL
            doi: str | None = None
            if "doi.org" in url:
                # Extract DOI from doi.org/10.xxx/xxx
                parts = url.split("doi.org/")
                if len(parts) > 1:
                    doi = parts[1].split("?")[0].split("#")[0]
            elif "/10." in url and url.split("/10.")[1][:1].isdigit():
                # Try to find DOI pattern in URL
                doi_start = url.find("/10.")
                if doi_start > 0:
                    doi = url[doi_start + 1 :].split("?")[0].split("#")[0]

            # Try to identify source type from URL
            # Academic journals and preprint servers -> @article
            journal_hints = {
                "arxiv.org": "arXiv preprint",
                "pubmed": "PubMed",
                "ncbi.nlm.nih.gov": "PubMed",
                "nature.com": "Nature",
                "science.org": "Science",
                "ieee": "IEEE",
                "acm.org": "ACM",
                "springer": "Springer",
                "elsevier": "Elsevier",
                "wiley": "Wiley",
                "copernicus.org": "Copernicus",
                "agu.org": "AGU",
                "onlinelibrary.wiley.com": "Wiley",
            }

            # Government/research org reports -> @techreport or @misc
            report_hints = [
                "nasa.gov",
                "noaa.gov",
                "jpl.nasa.gov",
                "gsfc.nasa.gov",
            ]

            journal: str | None = None
            entry_type = "article"  # Default to article

            for hint, name in journal_hints.items():
                if hint in url.lower():
                    journal = name
                    entry_type = "article"
                    break
            else:
                # Check if it's a report/webpage
                for hint in report_hints:
                    if hint in url.lower():
                        entry_type = "misc"
                        break

            # Use title override if provided, otherwise generate from URL
            if title_override:
                title = title_override
            else:
                # Generate a title placeholder (will need enrichment)
                # Use the last path segment or domain
                path = str(parsed_url.path) if parsed_url.path else ""
                path_parts = path.strip("/").split("/") if path else []
                title_hint = path_parts[-1] if path_parts else "Unknown"
                title = title_hint.replace("-", " ").replace("_", " ").title()
                if len(title) < 5:
                    title = f"Paper from {journal or 'unknown source'}"

            return Article(
                source=self.SOURCE_NAME,
                external_id=doi or url,
                entry_type=entry_type,
                title=title,  # Placeholder - needs enrichment
                authors=[],  # Unknown - needs enrichment
                year=None,  # Unknown - needs enrichment
                journal=journal,
                publication_type="article",
                doi=doi,
                abstract=None,  # Unknown - needs enrichment
                url=parsed_url,
                pdf_url=None,
                open_access="arxiv.org" in url.lower() or bool(doi),
                citation_count=None,
                accessed_date=date.today(),
            )

        except Exception as e:
            logger.debug(f"Failed to parse article from URL {url}: {e}")
            return None

    def _extract_content_and_citations(self, response: dict[str, Any]) -> tuple[str, list[str]]:
        """Extract both content and citation URLs from response.

        Args:
            response: The API response dict.

        Returns:
            Tuple of (content text, list of citation URLs).
        """
        content = ""
        citation_urls: list[str] = []

        choices = response.get("choices", [])
        if choices and isinstance(choices, list):
            message = choices[0].get("message", {})
            if isinstance(message, dict):
                content = message.get("content", "")
                # Check for citations in message metadata
                cites = message.get("citations")
                if cites and isinstance(cites, list):
                    citation_urls.extend(str(c) for c in cites if isinstance(c, str))

        # Also check response-level citations
        response_citations = response.get("citations")
        if response_citations and isinstance(response_citations, list):
            citation_urls.extend(str(c) for c in response_citations if isinstance(c, str))

        return content, list(set(citation_urls))

    def _extract_titles_from_content(self, content: str) -> list[tuple[str, str | None]]:
        """Extract paper titles from Perplexity content.

        Tries to find paper titles in the response text.

        Args:
            content: The response content text.

        Returns:
            List of tuples (title, url_hint).
        """
        import re

        titles: list[tuple[str, str | None]] = []

        # Look for numbered citations like [1], [2], etc.
        citation_pattern = r"\[(\d+)\]\s*(.*?)(?=\[\d+\]|$)"
        matches = re.findall(citation_pattern, content, re.DOTALL)

        for _num, text in matches:
            # Clean up the text
            text = text.strip()
            # Try to find a title - look for quoted text or first sentence
            title_match = re.search(r'["""]([^"""]+)["""]', text)
            if title_match:
                title = title_match.group(1).strip()
            else:
                # Take first line or first 100 chars
                first_line = text.split("\n")[0].strip()
                title = first_line[:150] if len(first_line) > 150 else first_line

            # Try to find a URL in the text
            url_match = re.search(r'https?://[^\s\)\]<>"{}|\\^`[\]]+', text)
            url_hint = url_match.group(0) if url_match else None

            if title and len(title) > 10:
                titles.append((title, url_hint))

        return titles

    def _extract_articles_from_response(self, response: dict[str, Any]) -> list[Article]:
        """Extract Article objects from Perplexity response.

        Uses rich annotations from OpenRouter/Perplexity which include
        both URLs and titles.

        Args:
            response: The API response dict.

        Returns:
            List of Article objects (may need enrichment).
        """
        # First try to get structured annotations (best quality)
        annotations = self._extract_annotations(response)

        if annotations:
            logger.debug(f"Extracted {len(annotations)} structured annotations from Perplexity")
            articles: list[Article] = []
            for ann in annotations:
                url = ann.get("url", "")
                title = ann.get("title", "")
                if url:
                    article = self._parse_article_from_url(url, title_override=title or None)
                    if article:
                        articles.append(article)
            return articles

        # Fallback: parse from content and citation URLs
        content, citation_urls = self._extract_content_and_citations(response)
        titles = self._extract_titles_from_content(content)

        logger.debug(
            f"No annotations found. Extracted {len(citation_urls)} URLs and {len(titles)} titles from content"
        )

        if not citation_urls and not titles:
            logger.warning("No citations or titles found in Perplexity response")
            return []

        # Create articles from citations, trying to match with titles
        matched_articles: list[Article] = []
        used_urls: set[str] = set()

        # First, try to match titles with URLs
        for title, url_hint in titles:
            if url_hint and url_hint in citation_urls:
                article = self._parse_article_from_url(url_hint, title_override=title)
                if article:
                    matched_articles.append(article)
                    used_urls.add(url_hint)
            else:
                # Title without matching URL - create placeholder
                article = Article(
                    source=self.SOURCE_NAME,
                    external_id=title[:50],
                    title=title,
                    authors=[],
                    year=None,
                    journal=None,
                    publication_type="article",
                    doi=None,
                    abstract=None,
                    url=None,
                    pdf_url=None,
                    open_access=False,
                    citation_count=None,
                )
                matched_articles.append(article)

        # Add remaining URLs without titles
        for url in citation_urls:
            if url not in used_urls:
                article = self._parse_article_from_url(url)
                if article:
                    matched_articles.append(article)

        return matched_articles

    def _do_search(self, query: str, limit: int) -> list[Article]:
        """Internal search method (without timeout wrapper)."""
        system_prompt = """You are an academic research assistant. Your task is to find peer-reviewed scientific papers that are relevant to the user's query.

When responding:
1. Search for and identify the most relevant academic papers
2. Focus on papers from reputable journals, conferences, and preprint servers
3. Prioritize papers with high citation counts and recent publications when relevant
4. Always include source URLs for the papers you reference

Use [1], [2], [3] etc. to cite sources in your response. The system will extract these citations."""

        user_prompt = f"""Find academic papers related to this claim or topic:

"{query}"

Please provide:
1. The most relevant papers with their titles
2. Publication years when available
3. First authors when available
4. Source URLs (DOI links, arXiv URLs, or publisher websites)

Focus on papers that would provide authoritative citations for this claim."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"Searching Perplexity for: '{query[:50]}...' (limit={limit})")

        response = self._make_request(messages)
        articles = self._extract_articles_from_response(response)

        # Log the response content for debugging
        choices = response.get("choices", [])
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        logger.debug(f"Perplexity response length: {len(content)} chars")

        logger.info(f"Perplexity returned {len(articles)} articles")
        return articles[:limit]

    @timed
    def search(
        self,
        query: str,
        limit: int = 10,
        timeout: float = DEFAULT_SEARCH_TIMEOUT,
    ) -> list[Article]:
        """Search for academic papers using Perplexity Sonar.

        Uses a carefully crafted prompt to find relevant papers
        and returns Article objects. Note: these Articles will
        need enrichment since Perplexity returns URLs, not
        full metadata.

        Args:
            query: Search query string (e.g., claim to find citations for).
            limit: Maximum number of results to return.
            timeout: Maximum time to wait for results (default: 30s).

        Returns:
            List of Article objects (may have incomplete metadata). Empty list if timeout.
        """
        try:
            return run_with_timeout(self._do_search, timeout, query, limit)
        except TimeoutError:
            logger.warning(
                f"Perplexity search timed out after {timeout}s for query: {query[:50]}..."
            )
            return []
        except Exception as e:
            logger.error(f"Unexpected error in Perplexity search: {e}")
            return []

    def search_with_fallback(
        self,
        query: str,
        limit: int = 10,
        min_results_threshold: int = 3,
    ) -> list[Article]:
        """Search with automatic retry using stronger model if needed.

        If the initial search returns fewer results than the threshold,
        automatically retry with sonar-pro for better quality.

        Args:
            query: Search query string.
            limit: Maximum number of results to return.
            min_results_threshold: Minimum acceptable results before retry.

        Returns:
            List of Article objects.
        """
        articles = self.search(query, limit=limit)

        if len(articles) < min_results_threshold and self.model == "perplexity/sonar":
            logger.info(f"Only {len(articles)} results from sonar, retrying with sonar-pro...")
            # Temporarily switch to pro model
            original_model = self.model
            self.model = "perplexity/sonar-pro"
            try:
                articles = self.search(query, limit=limit)
            finally:
                self.model = original_model

        return articles
