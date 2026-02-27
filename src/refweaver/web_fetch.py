"""Web content fetching utilities for RefWeaver.

Provides functions to fetch and extract text content from article landing pages.
Uses Selenium as primary method since many publisher sites require JavaScript.
"""

from typing import TYPE_CHECKING

import requests
from loguru import logger

if TYPE_CHECKING:
    from refweaver.models import Article


def _fetch_with_selenium(url: str, timeout: int = 30) -> str:
    """Fetch HTML using Selenium (handles JavaScript-heavy sites).

    Args:
        url: URL to fetch.
        timeout: Page load timeout in seconds.

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
        driver.set_page_load_timeout(timeout)
        driver.get(url)

        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Give extra time for JavaScript to render content
        import time

        time.sleep(2)

        html = driver.page_source
        logger.debug(f"Selenium successfully fetched page: {len(html)} chars")

        # Check if we got a "JavaScript required" message
        if (
            "javascript" in html.lower()
            and ("enable" in html.lower() or "required" in html.lower())
            and len(html) < 5000  # Likely just a JS warning page
        ):
            logger.warning("Page requires JavaScript but content may not have loaded properly")

        return html
    finally:
        if driver:
            driver.quit()


def _fetch_with_requests(url: str, timeout: int) -> str:
    """Fetch HTML using requests (faster but may not work on JS-heavy sites).

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
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"),
        "Accept-Language": "en-US,en;q=0.5",
    }

    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response.text


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
            ".article-body",
            ".full-text",
            "#main-content",
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


def fetch_article_landing_page(
    article: "Article",
    timeout: int = 30,
    use_selenium: bool = False,
) -> str | None:
    """Fetch and extract text content from an article's landing page.

    By default uses Selenium to handle JavaScript-heavy publisher sites.
    Falls back to requests if Selenium fails.

    Args:
        article: The Article to fetch content for.
        timeout: Page load timeout in seconds.
        use_selenium: Whether to use Selenium (default: True).

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
        url = str(article.pdf_url)

    if not url:
        logger.warning(f"No URL available for article: {article.title[:50]}...")
        return None

    html_content: str | None = None

    # Strategy 1: Use requests (faster but may not work on JS-heavy sites)
    if not use_selenium:
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

            # Detect "JavaScript required" pages
            if len(html_content) < 3000:
                soup_text = html_content.lower()
                if "javascript" in soup_text and ("enable" in soup_text or "required" in soup_text):
                    logger.warning("Page appears to require JavaScript but Selenium not used")

        except requests.RequestException as e:
            logger.error(f"Failed to fetch landing page {url}: {e}")
            error_response: requests.Response | None = getattr(e, "response", None)
            status_code = error_response.status_code if error_response else None
            if status_code == 403:
                use_selenium = True
            else:
                return None

    # Strategy 2: Use Selenium (handles JavaScript-heavy sites)
    if use_selenium and html_content is None:
        try:
            logger.debug(f"Fetching landing page with Selenium: {url}")
            html_content = _fetch_with_selenium(url)
            logger.debug(f"Selenium succeeded: {len(html_content)} chars")
        except Exception as e:
            logger.warning(f"Selenium failed ({e}), giving up")
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


async def fetch_article_landing_page_async(
    article: "Article", timeout: int = 30, use_selenium: bool = True
) -> str | None:
    """Async version of fetch_article_landing_page.

    Note: Selenium is synchronous, so this will run it in a thread.
    """
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, fetch_article_landing_page, article, timeout, use_selenium
    )
