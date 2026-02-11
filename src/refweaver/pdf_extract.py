"""PDF text extraction utilities for RefWeaver.

Provides functions to download and extract text from PDF files,
particularly useful for open-access articles.
"""

import re
from typing import TYPE_CHECKING

import requests
from loguru import logger

from refweaver.rate_limit import rate_limit_url

if TYPE_CHECKING:
    from refweaver.models import Article


# Common DOI patterns
DOI_PATTERNS = [
    # Standard DOI pattern: 10.xxxx/...
    r'10\.\d{4,}/[^\s"<>]+',
    # DOI with "doi.org/" or "doi:" prefix
    r'(?:doi\.org/|doi:\s*)10\.\d{4,}/[^\s"<>]+',
    # DOI in URL format
    r'https?://(?:dx\.)?doi\.org/10\.\d{4,}/[^\s"<>]+',
]


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes.

    Args:
        pdf_bytes: Raw PDF file content.

    Returns:
        Extracted text content.
    """
    try:
        import pymupdf

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            text_str = text if isinstance(text, str) else ""
            if text_str.strip():
                text_parts.append(text_str)

        doc.close()
        return "\n\n".join(text_parts)

    except Exception as e:
        logger.error(f"PDF text extraction failed: {e}")
        return ""


def download_and_extract_pdf(url: str, timeout: int = 60) -> str | None:
    """Download a PDF and extract its text content.

    Args:
        url: URL to the PDF file.
        timeout: Download timeout in seconds.

    Returns:
        Extracted text content, or None if download/extraction failed.
    """
    try:
        logger.debug(f"Downloading PDF from: {url}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        rate_limit_url(url)
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("content-type", "").lower()
        if "application/pdf" not in content_type and not url.endswith(".pdf"):
            logger.debug(f"URL does not point to PDF: {content_type}")
            return None

        # Download content
        pdf_bytes = response.content

        if len(pdf_bytes) < 1000:  # Too small to be a real PDF
            logger.warning(f"Downloaded file too small ({len(pdf_bytes)} bytes)")
            return None

        logger.info(f"Downloaded PDF: {len(pdf_bytes)} bytes")

        # Extract text
        text = extract_text_from_pdf_bytes(pdf_bytes)

        if text:
            logger.info(f"Extracted {len(text)} chars from PDF")
            return text
        else:
            logger.warning("No text extracted from PDF")
            return None

    except requests.RequestException as e:
        logger.error(f"Failed to download PDF {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing PDF {url}: {e}")
        return None


async def download_and_extract_pdf_async(url: str, timeout: int = 60) -> str | None:
    """Async version of download_and_extract_pdf."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()
            if "application/pdf" not in content_type and not url.endswith(".pdf"):
                return None

            pdf_bytes = response.content

            if len(pdf_bytes) < 1000:
                return None

            text = extract_text_from_pdf_bytes(pdf_bytes)
            return text if text else None

    except Exception as e:
        logger.error(f"Async PDF download failed for {url}: {e}")
        return None


def extract_doi_from_text(text: str) -> str | None:
    """Extract DOI from text content using multiple patterns.

    Args:
        text: Text content to search for DOI.

    Returns:
        Cleaned DOI string if found, None otherwise.
    """
    for pattern in DOI_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Clean up the DOI
            doi = match.strip()
            # Remove URL prefix if present
            doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
            doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
            # Remove trailing punctuation
            doi = doi.rstrip(".,;:)")
            # Basic validation: must start with 10.
            if doi.startswith("10.") and len(doi) > 8:
                return doi
    return None


def extract_doi_from_pdf_url(url: str, timeout: int = 60) -> str | None:
    """Download a PDF and extract DOI from its text content.

    Args:
        url: URL to the PDF file.
        timeout: Download timeout in seconds.

    Returns:
        Extracted DOI if found, None otherwise.
    """
    try:
        logger.debug(f"Downloading PDF to extract DOI: {url}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        rate_limit_url(url)
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("content-type", "").lower()
        if "application/pdf" not in content_type and not url.endswith(".pdf"):
            logger.debug(f"URL does not point to PDF: {content_type}")
            return None

        # Download content
        pdf_bytes = response.content

        if len(pdf_bytes) < 1000:  # Too small to be a real PDF
            logger.warning(f"Downloaded file too small ({len(pdf_bytes)} bytes)")
            return None

        logger.info(f"Downloaded PDF for DOI extraction: {len(pdf_bytes)} bytes")

        # Extract text from first few pages only (DOI is usually on first page)
        try:
            import pymupdf

            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []

            # Only check first 3 pages (DOI is almost always on first page)
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text = page.get_text()
                text_str = text if isinstance(text, str) else ""
                if text_str.strip():
                    text_parts.append(text_str)

            doc.close()
            text = "\n\n".join(text_parts)

        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return None

        if not text:
            logger.warning("No text extracted from PDF")
            return None

        # Extract DOI from the text
        doi = extract_doi_from_text(text)

        if doi:
            logger.info(f"Extracted DOI from PDF: {doi}")
        else:
            logger.debug("No DOI found in PDF text")

        return doi

    except requests.RequestException as e:
        logger.error(f"Failed to download PDF {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing PDF {url}: {e}")
        return None


def is_pdf_url(url: str) -> bool:
    """Check if a URL points to a PDF file.

    Args:
        url: URL to check.

    Returns:
        True if URL appears to be a PDF.
    """
    url_lower = url.lower()
    # Check common PDF indicators
    return (
        url_lower.endswith(".pdf")
        or "/pdf/" in url_lower
        or "/download/" in url_lower
        or "pdf=1" in url_lower
        or "download=1" in url_lower
    )


def try_get_fulltext_from_pdf(
    article: "Article",
    try_alternative_sources: bool = True,
    email: str | None = None,
) -> str | None:
    """Try to get full text from PDF using multiple sources.

    First tries the article's own pdf_url, then tries alternative sources
    (Unpaywall, Anna's Archive, direct DOI resolution) if enabled.

    Args:
        article: The Article to get PDF from.
        try_alternative_sources: Whether to try Unpaywall, Anna's Archive, etc.
        email: Email for Unpaywall API.

    Returns:
        Extracted text from PDF, or None if not available/failed.
    """
    # First, try the article's own pdf_url (if open access)
    if article.pdf_url and article.open_access:
        url = str(article.pdf_url)
        logger.info(f"Attempting to download PDF from article URL: {article.title[:50]}...")
        text = download_and_extract_pdf(url)
        if text:
            return text

    # Try alternative sources
    if try_alternative_sources:
        from refweaver.pdf_sources import find_pdf_url

        logger.info(f"Trying alternative sources for PDF: {article.title[:50]}...")
        alt_url = find_pdf_url(article, email=email)

        if alt_url:
            logger.info("Found alternative PDF URL, downloading...")
            return download_and_extract_pdf(alt_url)

    logger.debug(f"Could not get PDF text for: {article.title[:50]}...")
    return None
