"""Tests for sentence analysis pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from refweaver.analyzer import SentenceAnalyzer
from refweaver.llm import SearchKeywords, SentenceAnalysis, ArticleRelevance
from refweaver.models import Article, Sentence


class TestSentenceAnalyzer:
    """Test suite for SentenceAnalyzer."""

    def test_analyze_paragraph_single_sentence_no_ref(self):
        """Test analyzing a single sentence that doesn't need a reference."""
        mock_llm = MagicMock()
        mock_llm.analyze_sentence_needs_reference.return_value = {
            "needs_reference": False,
            "reason": "General statement, no specific claim",
        }

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        result = analyzer.analyze_paragraph("This is a simple sentence.")

        assert len(result) == 1
        assert result[0].text == "This is a simple sentence."
        assert result[0].needs_reference is False
        assert "General statement" in result[0].reason

    def test_analyze_paragraph_single_sentence_needs_ref(self):
        """Test analyzing a single sentence that needs a reference."""
        mock_llm = MagicMock()
        mock_llm.analyze_sentence_needs_reference.return_value = {
            "needs_reference": True,
            "reason": "Specific statistic requiring citation",
        }

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        result = analyzer.analyze_paragraph("The enzyme showed 95% efficiency.")

        assert len(result) == 1
        assert result[0].text == "The enzyme showed 95% efficiency."
        assert result[0].needs_reference is True
        assert "statistic" in result[0].reason

    def test_analyze_paragraph_multiple_sentences(self):
        """Test analyzing a paragraph with multiple sentences."""
        mock_llm = MagicMock()
        mock_llm.analyze_sentence_needs_reference.side_effect = [
            {"needs_reference": False, "reason": "General intro"},
            {"needs_reference": True, "reason": "Specific claim"},
            {"needs_reference": True, "reason": "Statistics cited"},
        ]

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        paragraph = "This is the introduction. It makes a specific claim. 95% of studies agree."
        result = analyzer.analyze_paragraph(paragraph)

        assert len(result) == 3
        assert result[0].needs_reference is False
        assert result[1].needs_reference is True
        assert result[2].needs_reference is True

    def test_analyze_paragraph_llm_called_with_context(self):
        """Test that LLM is called with proper context."""
        mock_llm = MagicMock()
        mock_llm.analyze_sentence_needs_reference.return_value = {
            "needs_reference": False,
            "reason": "Test",
        }

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        paragraph = "This is a test sentence."
        analyzer.analyze_paragraph(paragraph)

        mock_llm.analyze_sentence_needs_reference.assert_called_once()
        call_kwargs = mock_llm.analyze_sentence_needs_reference.call_args[1]
        assert call_kwargs["sentence"] == "This is a test sentence."
        assert call_kwargs["context"] == paragraph

    def test_analyze_sentences_multiple_paragraphs(self):
        """Test analyzing text with multiple paragraphs."""
        mock_llm = MagicMock()
        mock_llm.analyze_sentence_needs_reference.return_value = {
            "needs_reference": False,
            "reason": "Test",
        }

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        text = "First paragraph.\n\nSecond paragraph here."
        result = analyzer.analyze_sentences(text)

        # Should have 2 sentences total
        assert len(result) == 2
        assert all(isinstance(s, Sentence) for s in result)

    def test_sentence_model_immutable(self):
        """Test that Sentence model is immutable."""
        sentence = Sentence(
            text="Test sentence.",
            needs_reference=True,
            reason="Needs citation",
        )

        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            sentence.text = "Modified sentence."

    def test_sentence_model_equality(self):
        """Test Sentence model equality."""
        s1 = Sentence(
            text="Test sentence.",
            needs_reference=True,
            reason="Needs citation",
        )
        s2 = Sentence(
            text="Test sentence.",
            needs_reference=True,
            reason="Needs citation",
        )
        s3 = Sentence(
            text="Different sentence.",
            needs_reference=True,
            reason="Needs citation",
        )

        assert s1 == s2
        assert s1 != s3


class TestGenerateSearchKeywords:
    """Test suite for keyword generation using pydantic-ai."""

    def test_generate_keywords_delegates_to_llm(self):
        """Test that generate_search_keywords delegates to LLM client."""
        mock_llm = MagicMock()
        mock_llm.generate_search_keywords.return_value = [
            "enzyme-nanoparticle hybrid",
            "gold nanoparticle stabilization",
            "protein denaturation resistance",
        ]

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        result = analyzer.generate_search_keywords(
            "Gold nanoparticles stabilize enzymes against denaturation."
        )

        assert len(result) == 3
        assert "enzyme-nanoparticle hybrid" in result
        mock_llm.generate_search_keywords.assert_called_once_with(
            "Gold nanoparticles stabilize enzymes against denaturation."
        )

    def test_generate_keywords_accepts_sentence_object(self):
        """Test that generate_search_keywords accepts Sentence object."""
        mock_llm = MagicMock()
        mock_llm.generate_search_keywords.return_value = ["enzyme nanoparticle hybrid"]

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        sentence_obj = Sentence(
            text="Gold nanoparticles stabilize enzymes effectively.",
            needs_reference=True,
            reason="Specific claim about enzyme stabilization",
        )
        result = analyzer.generate_search_keywords(sentence_obj)

        assert len(result) == 1
        # Should extract text from Sentence object
        mock_llm.generate_search_keywords.assert_called_once_with(
            "Gold nanoparticles stabilize enzymes effectively."
        )

    def test_generate_keywords_uses_fallback(self):
        """Test fallback when LLM fails."""
        mock_llm = MagicMock()
        mock_llm.generate_search_keywords.return_value = ["fallback keyword"]

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        sentence = "This is a test sentence for fallback."
        result = analyzer.generate_search_keywords(sentence)

        assert len(result) == 1
        assert result[0] == "fallback keyword"


class TestEvaluateArticleRelevance:
    """Test suite for article relevance evaluation using pydantic-ai."""

    def test_evaluate_relevance_yes(self):
        """Test evaluation when article is relevant."""
        mock_llm = MagicMock()
        mock_llm.evaluate_article_relevance.return_value = {
            "relevant": True,
            "confidence": 0.85,
            "reasoning": "Article directly supports the claim with experimental data.",
        }

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        article = Article(
            source="test",
            external_id="123",
            title="Test Article Title",
            authors=["Author One", "Author Two"],
            year=2024,
            abstract="This is the abstract of the test article.",
        )

        result = analyzer.evaluate_article_relevance(
            "Gold nanoparticles stabilize enzymes.",
            article,
        )

        assert result["relevant"] is True
        assert result["confidence"] == 0.85
        assert "experimental data" in result["reasoning"]

    def test_evaluate_relevance_no(self):
        """Test evaluation when article is not relevant."""
        mock_llm = MagicMock()
        mock_llm.evaluate_article_relevance.return_value = {
            "relevant": False,
            "confidence": 0.90,
            "reasoning": "Article discusses unrelated topic.",
        }

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        article = Article(
            source="test",
            external_id="456",
            title="Unrelated Article",
            authors=["Author"],
            abstract="Different topic entirely.",
        )

        result = analyzer.evaluate_article_relevance(
            "Climate change affects glaciers.",
            article,
        )

        assert result["relevant"] is False
        assert result["confidence"] == 0.90
        assert "unrelated" in result["reasoning"].lower()

    def test_evaluate_relevance_accepts_sentence_object(self):
        """Test that evaluate_article_relevance accepts Sentence object."""
        mock_llm = MagicMock()
        mock_llm.evaluate_article_relevance.return_value = {
            "relevant": True,
            "confidence": 0.80,
            "reasoning": "Directly supports the claim.",
        }

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        sentence_obj = Sentence(
            text="Gold nanoparticles show 90% enzyme stabilization at high temperatures.",
            needs_reference=True,
            reason="Specific statistic needing citation",
        )
        article = Article(
            source="test",
            external_id="support123",
            title="Supporting Article",
            authors=["Researcher"],
            abstract="Shows enzyme stabilization data.",
        )

        result = analyzer.evaluate_article_relevance(sentence_obj, article)

        assert result["relevant"] is True
        assert result["confidence"] == 0.80
        # Should extract text from Sentence object and pass article fields
        mock_llm.evaluate_article_relevance.assert_called_once()
        call_kwargs = mock_llm.evaluate_article_relevance.call_args[1]
        assert "Gold nanoparticles show 90% enzyme stabilization" in call_kwargs["sentence"]
        assert call_kwargs["article_title"] == "Supporting Article"
        assert call_kwargs["article_authors"] == ["Researcher"]
        assert call_kwargs["article_abstract"] == "Shows enzyme stabilization data."

    def test_evaluate_relevance_missing_abstract(self):
        """Test evaluation when article has no abstract."""
        mock_llm = MagicMock()
        mock_llm.evaluate_article_relevance.return_value = {
            "relevant": False,
            "confidence": 0.5,
            "reasoning": "No abstract available.",
        }

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        article = Article(
            source="test",
            external_id="noabs",
            title="No Abstract Article",
            authors=["Author"],
            abstract=None,
        )

        result = analyzer.evaluate_article_relevance("Test.", article)

        assert result["relevant"] is False
        # Verify None is passed for abstract
        mock_llm.evaluate_article_relevance.assert_called_once()
        call_kwargs = mock_llm.evaluate_article_relevance.call_args[1]
        assert call_kwargs["article_abstract"] is None

    def test_evaluate_relevance_passes_article_fields(self):
        """Test that all article fields are passed to LLM client."""
        mock_llm = MagicMock()
        mock_llm.evaluate_article_relevance.return_value = {
            "relevant": True,
            "confidence": 0.75,
            "reasoning": "Good match.",
        }

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        article = Article(
            source="test",
            external_id="abc",
            title="Specific Research Title",
            authors=["Alice Smith", "Bob Jones", "Carol White", "David Lee"],
            year=2023,
            abstract="Detailed abstract here.",
        )

        analyzer.evaluate_article_relevance("Test claim.", article)

        mock_llm.evaluate_article_relevance.assert_called_once()
        call_kwargs = mock_llm.evaluate_article_relevance.call_args[1]
        assert call_kwargs["sentence"] == "Test claim."
        assert call_kwargs["article_title"] == "Specific Research Title"
        assert call_kwargs["article_authors"] == ["Alice Smith", "Bob Jones", "Carol White", "David Lee"]
        assert call_kwargs["article_year"] == 2023
        assert call_kwargs["article_abstract"] == "Detailed abstract here."
