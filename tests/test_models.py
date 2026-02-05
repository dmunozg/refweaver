"""Tests for RefWeaver data models."""

from datetime import date

import pytest
from pydantic import HttpUrl, ValidationError

from refweaver.models import Article


class TestArticle:
    """Test suite for Article model."""

    def test_create_article(self):
        """Test creating a basic Article."""
        article = Article(
            source="semanticscholar",
            external_id="12345",
            title="Test Article",
            authors=["Author One", "Author Two"],
        )

        assert article.source == "semanticscholar"
        assert article.external_id == "12345"
        assert article.title == "Test Article"
        assert article.authors == ["Author One", "Author Two"]
        assert article.retrieved_at == date.today()

    def test_article_with_all_fields(self):
        """Test creating an Article with all fields populated."""
        article = Article(
            source="openalex",
            external_id="W123456789",
            title="Full Test Article",
            authors=["Alice Smith", "Bob Jones"],
            year=2024,
            journal="Nature",
            publication_type="article",
            volume="45",
            issue="3",
            pages="123-145",
            doi="10.1234/example.5678",
            abstract="This is the abstract.",
            url=HttpUrl("https://example.com/paper"),
            pdf_url=HttpUrl("https://example.com/paper.pdf"),
            open_access=True,
            citation_count=42,
        )

        assert article.year == 2024
        assert article.journal == "Nature"
        assert article.publication_type == "article"
        assert article.volume == "45"
        assert article.issue == "3"
        assert article.pages == "123-145"
        assert article.doi == "10.1234/example.5678"
        assert article.abstract == "This is the abstract."
        assert str(article.url) == "https://example.com/paper"
        assert str(article.pdf_url) == "https://example.com/paper.pdf"
        assert article.open_access is True
        assert article.citation_count == 42

    def test_article_defaults(self):
        """Test Article default values."""
        article = Article(
            source="scholarly",
            external_id="abc123",
            title="Default Test",
            authors=["Single Author"],
        )

        assert article.publication_type == "article"
        assert article.open_access is False
        assert article.year is None
        assert article.journal is None
        assert article.doi is None
        assert article.abstract is None
        assert article.url is None
        assert article.pdf_url is None
        assert article.citation_count is None

    def test_article_immutability(self):
        """Test that Article is immutable."""
        article = Article(
            source="test",
            external_id="123",
            title="Immutable",
            authors=["Author"],
        )

        # Frozen models raise ValidationError on modification
        with pytest.raises(ValidationError):
            article.title = "New Title"

    def test_article_equality(self):
        """Test Article equality."""
        article1 = Article(
            source="test",
            external_id="123",
            title="Same",
            authors=["Author"],
        )
        article2 = Article(
            source="test",
            external_id="123",
            title="Same",
            authors=["Author"],
        )

        assert article1 == article2

    def test_article_different_sources(self):
        """Test Articles from different sources are not equal."""
        article1 = Article(
            source="semanticscholar",
            external_id="123",
            title="Paper",
            authors=["Author"],
        )
        article2 = Article(
            source="openalex",
            external_id="123",
            title="Paper",
            authors=["Author"],
        )

        assert article1 != article2
