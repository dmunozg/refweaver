"""Tests for the Semantic Scholar adapter."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from refweaver.adapters.semantic_scholar import SemanticScholarAdapter
from refweaver.models import Article


class TestSemanticScholarAdapter:
    """Test suite for SemanticScholarAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create a SemanticScholarAdapter instance."""
        return SemanticScholarAdapter()

    @pytest.fixture
    def mock_paper_object(self):
        """Create a mock Semantic Scholar paper object."""
        author1 = MagicMock()
        author1.name = "John Doe"
        author2 = MagicMock()
        author2.name = "Jane Smith"
        paper = MagicMock()
        paper.paperId = "12345678"
        paper.title = "Test Paper Title"
        paper.authors = [author1, author2]
        paper.year = 2024
        paper.venue = "Nature"
        paper.publicationTypes = ["article"]
        paper.volume = "45"
        paper.issue = "3"
        paper.pages = "123-145"
        paper.doi = "10.1234/test.5678"
        paper.abstract = "This is a test abstract."
        paper.url = "https://semanticscholar.org/paper/12345678"
        paper.openAccessPdf = {"url": "https://pdf.example.com/paper.pdf"}
        paper.isOpenAccess = True
        paper.citationCount = 42
        return paper

    @pytest.fixture
    def mock_paper_dict(self):
        """Create a mock Semantic Scholar paper as dict."""
        return {
            "paperId": "87654321",
            "title": "Dict Test Paper",
            "authors": [
                {"name": "Alice Johnson"},
                {"name": "Bob Brown"},
            ],
            "year": 2023,
            "venue": "Science",
            "publicationTypes": ["review"],
            "volume": "12",
            "issue": "1",
            "pages": "1-20",
            "doi": "10.5678/dict.9012",
            "abstract": "Another test abstract.",
            "url": "https://semanticscholar.org/paper/87654321",
            "openAccessPdf": {"url": "https://pdf.example.com/dict.pdf"},
            "isOpenAccess": True,
            "citationCount": 100,
        }

    def test_source_name(self, adapter):
        """Test that SOURCE_NAME is correct."""
        assert adapter.SOURCE_NAME == "semanticscholar"

    def test_parse_authors_with_dicts(self, adapter):
        """Test parsing authors from dict format."""
        authors = [{"name": "Author One"}, {"name": "Author Two"}]
        result = adapter._parse_authors(authors)
        assert result == ["Author One", "Author Two"]

    def test_parse_authors_with_objects(self, adapter):
        """Test parsing authors from object format."""
        mock_author = MagicMock()
        mock_author.name = "Obj Author"
        authors = [mock_author]
        result = adapter._parse_authors(authors)
        assert result == ["Obj Author"]

    def test_parse_authors_skips_empty(self, adapter):
        """Test that empty author names are skipped."""
        authors = [{"name": "Valid Author"}, {"name": None}, {"name": ""}]
        result = adapter._parse_authors(authors)
        assert result == ["Valid Author"]

    def test_to_article_from_object(self, adapter, mock_paper_object):
        """Test converting a paper object to Article."""
        article = adapter._to_article(mock_paper_object)

        assert isinstance(article, Article)
        assert article.source == "semanticscholar"
        assert article.external_id == "12345678"
        assert article.title == "Test Paper Title"
        assert article.authors == ["John Doe", "Jane Smith"]
        assert article.year == 2024
        assert article.journal == "Nature"
        assert article.publication_type == "article"
        assert article.volume == "45"
        assert article.issue == "3"
        assert article.pages == "123-145"
        assert article.doi == "10.1234/test.5678"
        assert article.abstract == "This is a test abstract."
        assert str(article.url) == "https://semanticscholar.org/paper/12345678"
        assert str(article.pdf_url) == "https://pdf.example.com/paper.pdf"
        assert article.open_access is True
        assert article.citation_count == 42
        assert article.retrieved_at == date.today()

    def test_to_article_from_dict(self, adapter, mock_paper_dict):
        """Test converting a paper dict to Article."""
        article = adapter._to_article(mock_paper_dict)

        assert isinstance(article, Article)
        assert article.external_id == "87654321"
        assert article.title == "Dict Test Paper"
        assert article.authors == ["Alice Johnson", "Bob Brown"]
        assert article.year == 2023
        assert article.journal == "Science"
        assert article.publication_type == "review"
        assert article.citation_count == 100

    def test_to_article_missing_optional_fields(self, adapter):
        """Test conversion with minimal data."""
        paper = MagicMock()
        paper.paperId = "minimal123"
        paper.title = "Minimal Paper"
        paper.authors = []
        paper.year = None
        paper.venue = None
        paper.publicationTypes = None
        paper.volume = None
        paper.issue = None
        paper.pages = None
        paper.doi = None
        paper.abstract = None
        paper.url = None
        paper.openAccessPdf = None
        paper.isOpenAccess = None
        paper.citationCount = None

        article = adapter._to_article(paper)

        assert article.external_id == "minimal123"
        assert article.title == "Minimal Paper"
        assert article.authors == []
        assert article.year is None
        assert article.journal is None
        assert article.publication_type == "article"  # Default
        assert article.open_access is False  # Default
        assert article.citation_count is None

    @patch("refweaver.adapters.semantic_scholar.SemanticScholar")
    def test_search(self, mock_s2_class, adapter):
        """Test search method."""
        # Setup mock
        mock_paper = MagicMock()
        mock_paper.paperId = "search123"
        mock_paper.title = "Search Result"
        mock_paper.authors = []
        mock_paper.year = 2024
        mock_paper.venue = None
        mock_paper.publicationTypes = None
        mock_paper.volume = None
        mock_paper.issue = None
        mock_paper.pages = None
        mock_paper.doi = None
        mock_paper.abstract = None
        mock_paper.url = None
        mock_paper.openAccessPdf = None
        mock_paper.isOpenAccess = None
        mock_paper.citationCount = None

        mock_client = MagicMock()
        mock_client.search_paper.return_value = [mock_paper]
        mock_s2_class.return_value = mock_client

        # Create new adapter with mocked client
        test_adapter = SemanticScholarAdapter()
        test_adapter.client = mock_client

        # Test
        results = test_adapter.search("test query", limit=5)

        assert len(results) == 1
        assert results[0].external_id == "search123"
        assert results[0].title == "Search Result"
        mock_client.search_paper.assert_called_once_with(
            query="test query",
            limit=5,
            fields=[
                "paperId",
                "title",
                "authors",
                "year",
                "venue",
                "publicationTypes",
                "volume",
                "issue",
                "pages",
                "doi",
                "abstract",
                "url",
                "openAccessPdf",
                "isOpenAccess",
                "citationCount",
            ],
        )

    @patch("refweaver.adapters.semantic_scholar.SemanticScholar")
    def test_get_paper_by_doi_success(self, mock_s2_class):
        """Test fetching paper by DOI successfully."""
        mock_paper = MagicMock()
        mock_paper.paperId = "doi123"
        mock_paper.title = "DOI Paper"
        mock_paper.authors = []
        mock_paper.year = None
        mock_paper.venue = None
        mock_paper.publicationTypes = None
        mock_paper.volume = None
        mock_paper.issue = None
        mock_paper.pages = None
        mock_paper.doi = None
        mock_paper.abstract = None
        mock_paper.url = None
        mock_paper.openAccessPdf = None
        mock_paper.isOpenAccess = None
        mock_paper.citationCount = None

        mock_client = MagicMock()
        mock_client.get_paper.return_value = mock_paper
        mock_s2_class.return_value = mock_client

        adapter = SemanticScholarAdapter()
        adapter.client = mock_client

        result = adapter.get_paper_by_doi("10.1234/test")

        assert result is not None
        assert result.external_id == "doi123"
        assert result.title == "DOI Paper"
        mock_client.get_paper.assert_called_once_with("10.1234/test")

    @patch("refweaver.adapters.semantic_scholar.SemanticScholar")
    def test_get_paper_by_doi_not_found(self, mock_s2_class):
        """Test fetching paper by DOI when not found."""
        mock_client = MagicMock()
        mock_client.get_paper.side_effect = Exception("Paper not found")
        mock_s2_class.return_value = mock_client

        adapter = SemanticScholarAdapter()
        adapter.client = mock_client

        result = adapter.get_paper_by_doi("10.9999/invalid")

        assert result is None

    @patch("refweaver.adapters.semantic_scholar.SemanticScholar")
    def test_get_paper_by_id_success(self, mock_s2_class):
        """Test fetching paper by ID successfully."""
        mock_paper = MagicMock()
        mock_paper.paperId = "corpus123"
        mock_paper.title = "Corpus Paper"
        mock_paper.authors = []
        mock_paper.year = None
        mock_paper.venue = None
        mock_paper.publicationTypes = None
        mock_paper.volume = None
        mock_paper.issue = None
        mock_paper.pages = None
        mock_paper.doi = None
        mock_paper.abstract = None
        mock_paper.url = None
        mock_paper.openAccessPdf = None
        mock_paper.isOpenAccess = None
        mock_paper.citationCount = None

        mock_client = MagicMock()
        mock_client.get_paper.return_value = mock_paper
        mock_s2_class.return_value = mock_client

        adapter = SemanticScholarAdapter()
        adapter.client = mock_client

        result = adapter.get_paper_by_id("12345")

        assert result is not None
        assert result.external_id == "corpus123"
        mock_client.get_paper.assert_called_once_with("CorpusId:12345")

    def test_article_immutability(self, adapter, mock_paper_object):
        """Test that Article models are immutable."""
        article = adapter._to_article(mock_paper_object)

        with pytest.raises(ValidationError):
            article.title = "New Title"
