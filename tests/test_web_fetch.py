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
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://example.com/article"
        assert "headers" in call_args[1]

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
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://doi.org/10.1234/example"

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

    @patch("refweaver.web_fetch.requests.get")
    @patch("refweaver.web_fetch._fetch_with_selenium")
    def test_fetch_403_fallback_to_selenium(self, mock_selenium, mock_requests):
        """Test that 403 errors trigger Selenium fallback."""
        from requests import HTTPError

        # Simulate 403 response
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_requests.side_effect = HTTPError("403 Forbidden", response=mock_response)

        # Selenium succeeds
        mock_selenium.return_value = (
            "<html><body><article><p>Selenium fetched content</p></article></body></html>"
        )

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
        assert "Selenium fetched content" in result
        mock_selenium.assert_called_once_with("https://example.com/article")

    @patch("refweaver.web_fetch.requests.get")
    @patch("refweaver.web_fetch._fetch_with_selenium")
    def test_fetch_selenium_also_fails(self, mock_selenium, mock_requests):
        """Test when both requests and Selenium fail."""
        from requests import HTTPError

        # Simulate 403 response
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_requests.side_effect = HTTPError("403 Forbidden", response=mock_response)

        # Selenium also fails
        mock_selenium.side_effect = Exception("Chrome not found")

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
