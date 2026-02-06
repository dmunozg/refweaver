"""PDF text extraction utilities for RefWeaver.

Provides functions to download and extract text from PDF files,
particularly useful for open-access articles.
"""

import io
from typing import TYPE_CHECKING

import requests
from loguru import logger

if TYPE_CHECKING:
    from refweaver.models import Article


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
            if text.strip():
                text_parts.append(text)

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


def try_get_fulltext_from_pdf(article: "Article") -> str | None:
    """Try to get full text from PDF URL if article is open access.

    Args:
        article: The Article to get PDF from.

    Returns:
        Extracted text from PDF, or None if not available/failed.
    """
    if not article.open_access:
        logger.debug(f"Article not open access, skipping PDF: {article.title[:50]}...")
        return None

    if not article.pdf_url:
        logger.debug(f"No PDF URL available: {article.title[:50]}...")
        return None

    url = str(article.pdf_url)
    logger.info(f"Attempting to download PDF for: {article.title[:50]}...")

    return download_and_extract_pdf(url)
