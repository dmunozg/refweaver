"""Web content fetching utilities for RefWeaver.

Provides functions to fetch and extract text content from article landing pages.
"""

from typing import TYPE_CHECKING

import requests
from loguru import logger

if TYPE_CHECKING:
    from refweaver.models import Article


def fetch_article_landing_page(article: "Article", timeout: int = 30) -> str | None:
    """Fetch and extract text content from an article's landing page.

    This is useful for open-access articles where the full text is available
    on the publisher's website. The extracted text can be used for more
    thorough LLM evaluation.

    Args:
        article: The Article to fetch content for.
        timeout: Request timeout in seconds.

    Returns:
        Extracted text content, or None if fetching failed.
    """
    if not article.open_access:
        logger.debug(f"Article '{article.title[:50]}...' is not open access, skipping fetch")
        return None

    # Determine URL to fetch
    url: str | None = None
    if article.url:
        url = str(article.url)
    elif article.doi:
        url = f"https://doi.org/{article.doi}"
    elif article.pdf_url:
        # Try the PDF URL as fallback
        url = str(article.pdf_url)

    if not url:
        logger.warning(f"No URL available for article: {article.title[:50]}...")
        return None

    try:
        logger.debug(f"Fetching landing page: {url}")
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("content-type", "").lower()

        if "application/pdf" in content_type:
            # It's a PDF, we can't extract text directly here
            logger.debug("URL points to PDF, skipping HTML extraction")
            return None

        if "text/html" not in content_type:
            logger.debug(f"Unexpected content type: {content_type}")
            return None

        # Extract text from HTML
        html_content = response.text
        text_content = extract_text_from_html(html_content)

        if text_content:
            logger.info(
                f"Extracted {len(text_content)} chars from landing page "
                f"for: {article.title[:50]}..."
            )
            return text_content
        else:
            logger.warning(f"No text extracted from landing page: {url}")
            return None

    except requests.RequestException as e:
        logger.error(f"Failed to fetch landing page {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing landing page {url}: {e}")
        return None


def extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML content.

    Args:
        html: Raw HTML content.

    Returns:
        Cleaned text content.
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()

        # Try to find main content area
        main_content = None
        for selector in [
            "article",
            "main",
            '[role="main"]',
            ".article-content",
            ".content",
            "#content",
            ".main-content",
        ]:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            # Fall back to body text
            text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)

        return cleaned_text

    except Exception as e:
        logger.error(f"HTML parsing failed: {e}")
        return ""


async def fetch_article_landing_page_async(
    article: "Article", timeout: int = 30
) -> str | None:
    """Async version of fetch_article_landing_page."""
    if not article.open_access:
        logger.debug(f"Article '{article.title[:50]}...' is not open access")
        return None

    url: str | None = None
    if article.url:
        url = str(article.url)
    elif article.doi:
        url = f"https://doi.org/{article.doi}"
    elif article.pdf_url:
        url = str(article.pdf_url)

    if not url:
        return None

    try:
        import httpx

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()

            if "application/pdf" in content_type:
                return None

            if "text/html" not in content_type:
                return None

            text_content = extract_text_from_html(response.text)

            if text_content:
                logger.info(
                    f"Extracted {len(text_content)} chars (async) from: {article.title[:50]}..."
                )
                return text_content
            return None

    except Exception as e:
        logger.error(f"Async fetch failed for {url}: {e}")
        return None
