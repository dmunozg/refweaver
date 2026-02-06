"""Web content fetching utilities for RefWeaver.

Provides functions to fetch and extract text content from article landing pages.
"""

from typing import TYPE_CHECKING

import requests
from loguru import logger

if TYPE_CHECKING:
    from refweaver.models import Article


def _fetch_with_requests(url: str, timeout: int) -> str:
    """Fetch HTML using requests with browser-like headers.

    Args:
        url: URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        HTML content.

    Raises:
        requests.RequestException: If the request fails.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
    }

    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response.text


def _fetch_with_selenium(url: str) -> str:
    """Fetch HTML using Selenium as fallback for bot detection.

    Args:
        url: URL to fetch.

    Returns:
        HTML content.

    Raises:
        Exception: If Selenium fails.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    logger.debug(f"Using Selenium to fetch: {url}")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        html = driver.page_source
        logger.debug(f"Selenium successfully fetched page: {len(html)} chars")
        return html
    finally:
        if driver:
            driver.quit()


def fetch_article_landing_page(article: "Article", timeout: int = 30) -> str | None:
    """Fetch and extract text content from an article's landing page.

    This is useful for open-access articles where the full text is available
    on the publisher's website. The extracted text can be used for more
    thorough LLM evaluation.

    First tries requests, falls back to Selenium on 403 Forbidden (bot detection).

    Args:
        article: The Article to fetch content for.
        timeout: Request timeout in seconds.

    Returns:
        Extracted text content, or None if fetching failed.
    """
    if not article.open_access:
        logger.debug(
            f"Article '{article.title[:50]}...' is not open access, skipping fetch"
        )
        return None

    # Determine URL to fetch
    url: str | None = None
    if article.url:
        url = str(article.url)
    elif article.doi:
        url = f"https://doi.org/{article.doi}"
    elif article.pdf_url:
        url = str(article.pdf_url)

    if not url:
        logger.warning(f"No URL available for article: {article.title[:50]}...")
        return None

    html_content: str | None = None

    # Strategy 1: Try requests with enhanced headers
    try:
        logger.debug(f"Fetching landing page with requests: {url}")
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("content-type", "").lower()

        if "application/pdf" in content_type:
            logger.debug("URL points to PDF, skipping HTML extraction")
            return None

        if "text/html" not in content_type:
            logger.debug(f"Unexpected content type: {content_type}")
            return None

        html_content = response.text
        logger.debug(f"Requests succeeded: {len(html_content)} chars")

    except requests.HTTPError as e:
        # Check if it's a 403 Forbidden - try Selenium fallback
        if e.response is not None and e.response.status_code == 403:
            logger.warning(f"Got 403 from {url}, falling back to Selenium")
        else:
            logger.debug(f"Requests failed ({e}), trying Selenium")

        # Strategy 2: Fall back to Selenium
        try:
            html_content = _fetch_with_selenium(url)
        except Exception as selenium_error:
            logger.error(f"Selenium also failed: {selenium_error}")
            return None

    except requests.RequestException as e:
        logger.error(f"Failed to fetch landing page {url}: {e}")
        return None

    # Extract text from HTML
    if html_content:
        try:
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
        except Exception as e:
            logger.error(f"Error processing landing page {url}: {e}")
            return None

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
