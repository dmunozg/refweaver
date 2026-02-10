"""Alternative PDF source resolvers for RefWeaver.

Tries multiple sources to find PDFs for articles, including:
- Unpaywall (legal open access finder)
- Anna's Archive
- Direct DOI resolution
"""

from typing import TYPE_CHECKING

import requests
from loguru import logger

if TYPE_CHECKING:
    from refweaver.models import Article


def resolve_pdf_via_unpaywall(article: "Article", email: str | None = None) -> str | None:
    """Try to find open access PDF via Unpaywall API.

    Unpaywall is a legal, non-profit service that finds open access
    versions of articles based on their DOI.

    Args:
        article: The Article to find PDF for.
        email: Email for Unpaywall API (optional but recommended).

    Returns:
        PDF URL if found, None otherwise.
    """
    if not article.doi:
        logger.debug(f"No DOI available for article: {article.title[:50]}...")
        return None

    try:
        # Use email from env or default
        if email is None:
            import os
            email = os.getenv("UNPAYWALL_EMAIL", "user@example.com")

        url = f"https://api.unpaywall.org/v2/{article.doi}"
        params = {"email": email}

        logger.debug(f"Querying Unpaywall for DOI: {article.doi}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Check for best open access location
        best_oa = data.get("best_oa_location")
        if best_oa:
            pdf_url = best_oa.get("pdf_url") or best_oa.get("url")
            if pdf_url:
                logger.info(f"Unpaywall found PDF for: {article.title[:50]}...")
                return str(pdf_url)

        # Check if article is OA but no direct PDF link
        if data.get("is_oa"):
            logger.debug("Article is OA but no direct PDF link from Unpaywall")

        return None

    except requests.RequestException as e:
        logger.error(f"Unpaywall request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unpaywall error: {e}")
        return None


def resolve_pdf_via_annas_archive(article: "Article") -> str | None:
    """Try to find PDF via Anna's Archive.

    Anna's Archive indexes multiple shadow libraries.

    Args:
        article: The Article to find PDF for.

    Returns:
        PDF URL if found, None otherwise.
    """
    if not article.doi and not article.title:
        return None

    try:
        # Anna's Archive has a search API
        # We can search by DOI or title + authors
        search_query = article.doi if article.doi else f"{article.title} {' '.join(article.authors[:2])}"

        logger.debug(f"Searching Anna's Archive for: {search_query[:60]}...")

        # Anna's Archive search endpoint
        search_url = "https://annas-archive.org/search"
        params = {"q": search_query, "type": "articles"}

        response = requests.get(search_url, params=params, timeout=15)
        response.raise_for_status()

        # Parse search results to find PDF link
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for download links - Anna's Archive has specific link patterns
        # This is a simplified version - actual implementation may need adjustment
        # based on their current page structure
        links = soup.find_all("a", href=True)

        for link in links:
            href_raw = link.get("href")
            href = str(href_raw) if href_raw is not None else ""
            if "/download/" in href or href.endswith(".pdf"):
                # Convert relative URL to absolute
                pdf_url = f"https://annas-archive.org{href}" if href.startswith("/") else href

                logger.info(f"Anna's Archive found PDF for: {article.title[:50]}...")
                return pdf_url

        return None

    except requests.RequestException as e:
        logger.error(f"Anna's Archive request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Anna's Archive error: {e}")
        return None


def resolve_pdf_via_direct_doi(article: "Article") -> str | None:
    """Try to resolve DOI directly to check for open access PDF.

    Some publishers redirect DOI to article page which may have OA PDF.

    Args:
        article: The Article to find PDF for.

    Returns:
        PDF URL if found, None otherwise.
    """
    if not article.doi:
        return None

    try:
        doi_url = f"https://doi.org/{article.doi}"

        logger.debug(f"Resolving DOI directly: {doi_url}")

        # Follow redirects
        response = requests.head(
            doi_url,
            allow_redirects=True,
            timeout=10,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
            },
        )

        final_url = response.url

        # Check if final URL is a PDF
        if final_url.endswith(".pdf"):
            logger.info(f"DOI resolved directly to PDF: {final_url}")
            return final_url

        # Try common PDF URL patterns
        # arXiv
        if "arxiv.org" in final_url:
            arxiv_id = final_url.split("/")[-1]
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        # bioRxiv / medRxiv
        if "biorxiv.org" in final_url or "medrxiv.org" in final_url:
            return final_url.replace("/content/", "/content/") + ".full.pdf"

        return None

    except requests.RequestException as e:
        logger.error(f"DOI resolution failed: {e}")
        return None


def find_pdf_url(article: "Article", email: str | None = None) -> str | None:
    """Try multiple sources to find a PDF URL for an article.

    Tries sources in order:
    1. Article's own pdf_url field
    2. Unpaywall (legal OA finder)
    3. Anna's Archive
    4. Direct DOI resolution

    Args:
        article: The Article to find PDF for.
        email: Email for Unpaywall API.

    Returns:
        PDF URL if found from any source, None otherwise.
    """
    # First, try the article's own pdf_url
    if article.pdf_url:
        logger.debug(f"Using article's own PDF URL: {article.pdf_url}")
        return str(article.pdf_url)

    # Try Unpaywall (legal, recommended)
    logger.info(f"Trying Unpaywall for: {article.title[:50]}...")
    pdf_url = resolve_pdf_via_unpaywall(article, email)
    if pdf_url:
        return pdf_url

    # Try Anna's Archive
    logger.info(f"Trying Anna's Archive for: {article.title[:50]}...")
    pdf_url = resolve_pdf_via_annas_archive(article)
    if pdf_url:
        return pdf_url

    # Try direct DOI resolution
    logger.info(f"Trying direct DOI resolution for: {article.title[:50]}...")
    pdf_url = resolve_pdf_via_direct_doi(article)
    if pdf_url:
        return pdf_url

    logger.warning(f"Could not find PDF for: {article.title[:50]}...")
    return None
