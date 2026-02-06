"""Tests for web fetch utilities."""

from unittest.mock import MagicMock, patch

import pytest

from refweaver.models import Article
from refweaver.web_fetch import (
    extract_text_from_html,
    fetch_article_landing_page,
)


class TestExtractTextFromHtml:
    """Test suite for HTML text extraction."""

    def test_extract_text_basic(self):
        """Test basic HTML text extraction."""
        html = "<html><body><p>Hello World</p></body></html>"
        result = extract_text_from_html(html)
        assert "Hello World" in result

    def test_extract_text_removes_scripts(self):
        """Test that script tags are removed."""
        html = """
        <html>
            <body>
                <script>alert('test')</script>
                <p>Visible content</p>
            </body>
        </html>
        """
        result = extract_text_from_html(html)
        assert "alert" not in result
        assert "Visible content" in result

    def test_extract_text_removes_styles(self):
        """Test that style tags are removed."""
        html = """
        <html>
            <body>
                <style>.class { color: red; }</style>
                <p>Visible content</p>
            </body>
        </html>
        """
        result = extract_text_from_html(html)
        assert "color: red" not in result
        assert "Visible content" in result

    def test_extract_text_main_content_priority(self):
        """Test that main/article tags are prioritized."""
        html = """
        <html>
            <body>
                <nav>Navigation menu</nav>
                <main>
                    <p>Main content here</p>
                </main>
                <footer>Footer content</footer>
            </body>
        </html>
        """
        result = extract_text_from_html(html)
        assert "Main content here" in result
        assert "Navigation" not in result


class TestFetchArticleLandingPage:
    """Test suite for fetching article landing pages."""

    def test_skip_non_open_access(self):
        """Test that non-open-access articles are skipped."""
        article = Article(
            source="test",
            external_id="123",
            title="Test Article",
            authors=["Author"],
            open_access=False,
        )

        result = fetch_article_landing_page(article)
        assert result is None

    @patch("refweaver.web_fetch.requests.get")
    def test_fetch_success(self, mock_get):
        """Test successful fetch and text extraction."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><article><p>Article content here</p></article></body></html>"
        mock_get.return_value = mock_response

        article = Article(
            source="test",
            external_id="123",
            title="Test Article",
            authors=["Author"],
            open_access=True,
            url="https://example.com/article",
        )

        result = fetch_article_landing_page(article)

        assert result is not None
        assert "Article content here" in result
        mock_get.assert_called_once_with(
            "https://example.com/article", timeout=30, allow_redirects=True
        )

    @patch("refweaver.web_fetch.requests.get")
    def test_fetch_pdf_content_type_skipped(self, mock_get):
        """Test that PDF content is skipped."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_get.return_value = mock_response

        article = Article(
            source="test",
            external_id="123",
            title="Test Article",
            authors=["Author"],
            open_access=True,
            url="https://example.com/article.pdf",
        )

        result = fetch_article_landing_page(article)

        assert result is None

    @patch("refweaver.web_fetch.requests.get")
    def test_fetch_doi_url_fallback(self, mock_get):
        """Test that DOI URL is used when no URL field."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><p>Content from DOI</p></body></html>"
        mock_get.return_value = mock_response

        article = Article(
            source="test",
            external_id="123",
            title="Test Article",
            authors=["Author"],
            open_access=True,
            doi="10.1234/example",
        )

        result = fetch_article_landing_page(article)

        assert result is not None
        mock_get.assert_called_once_with(
            "https://doi.org/10.1234/example", timeout=30, allow_redirects=True
        )

    @patch("refweaver.web_fetch.requests.get")
    def test_fetch_request_exception(self, mock_get):
        """Test handling of request exceptions."""
        from requests import RequestException

        mock_get.side_effect = RequestException("Connection error")

        article = Article(
            source="test",
            external_id="123",
            title="Test Article",
            authors=["Author"],
            open_access=True,
            url="https://example.com/article",
        )

        result = fetch_article_landing_page(article)

        assert result is None
