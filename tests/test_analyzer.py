"""Tests for sentence analysis pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from refweaver.analyzer import SentenceAnalyzer
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
    """Test suite for keyword generation."""

    def test_generate_keywords_basic(self):
        """Test basic keyword generation."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "enzyme-nanoparticle hybrid\n"
            "gold nanoparticle stabilization\n"
            "protein denaturation resistance"
        )
        mock_llm.client.chat.completions.create.return_value = mock_response

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        result = analyzer.generate_search_keywords(
            "Gold nanoparticles stabilize enzymes against denaturation."
        )

        assert len(result) == 3
        assert "enzyme-nanoparticle hybrid" in result
        assert "gold nanoparticle stabilization" in result
        assert "protein denaturation resistance" in result

    def test_generate_keywords_filters_empty_lines(self):
        """Test that empty lines are filtered from keywords."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "\n"
            "valid keyword one\n"
            "\n"
            "valid keyword two\n"
            "   \n"
        )
        mock_llm.client.chat.completions.create.return_value = mock_response

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        result = analyzer.generate_search_keywords("Test sentence.")

        assert len(result) == 2
        assert "valid keyword one" in result
        assert "valid keyword two" in result

    def test_generate_keywords_fallback_on_empty(self):
        """Test fallback to sentence when LLM returns empty."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "\n\n"
        mock_llm.client.chat.completions.create.return_value = mock_response

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        sentence = "This is a test sentence for fallback."
        result = analyzer.generate_search_keywords(sentence)

        assert len(result) == 1
        assert result[0] == sentence[:100]

    def test_generate_keywords_llm_called_with_system_prompt(self):
        """Test that LLM is called with proper system prompt."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test keyword"
        mock_llm.client.chat.completions.create.return_value = mock_response

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        analyzer.generate_search_keywords("Test sentence.")

        call_args = mock_llm.client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        assert messages[0]["role"] == "system"
        assert "academic search" in messages[0]["content"].lower()


class TestEvaluateArticleRelevance:
    """Test suite for article relevance evaluation."""

    def test_evaluate_relevance_yes(self):
        """Test evaluation when article is relevant."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "RELEVANT: YES\n"
            "CONFIDENCE: 0.85\n"
            "REASONING: Article directly supports the claim with experimental data."
        )
        mock_llm.client.chat.completions.create.return_value = mock_response

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
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "RELEVANT: NO\n"
            "CONFIDENCE: 0.90\n"
            "REASONING: Article discusses unrelated topic."
        )
        mock_llm.client.chat.completions.create.return_value = mock_response

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

    def test_evaluate_relevance_maybe_treated_as_yes(self):
        """Test that 'Maybe' relevance is treated as True."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "RELEVANT: Maybe\n"
            "CONFIDENCE: 0.60\n"
            "REASONING: Partially relevant but not perfect match."
        )
        mock_llm.client.chat.completions.create.return_value = mock_response

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        article = Article(
            source="test",
            external_id="789",
            title="Partially Related",
            authors=["Author"],
            abstract="Somewhat related content.",
        )

        result = analyzer.evaluate_article_relevance(
            "Test sentence.",
            article,
        )

        assert result["relevant"] is True  # Maybe is treated as relevant
        assert result["confidence"] == 0.60

    def test_evaluate_relevance_article_includes_title_authors(self):
        """Test that article metadata is included in the prompt."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "RELEVANT: YES\nCONFIDENCE: 0.5\nREASONING: Test"
        mock_llm.client.chat.completions.create.return_value = mock_response

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

        call_args = mock_llm.client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][1]["content"]
        assert "Specific Research Title" in prompt
        assert "Alice Smith" in prompt
        assert "Bob Jones" in prompt
        assert "Carol White" in prompt
        assert "et al." in prompt  # Should show et al. for 4+ authors
        assert "2023" in prompt
        assert "Detailed abstract here" in prompt

    def test_evaluate_relevance_clamps_confidence(self):
        """Test that confidence values are clamped to 0-1 range."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "RELEVANT: YES\n"
            "CONFIDENCE: 1.5\n"  # Over 1.0
            "REASONING: Test"
        )
        mock_llm.client.chat.completions.create.return_value = mock_response

        analyzer = SentenceAnalyzer(llm_client=mock_llm)
        article = Article(
            source="test",
            external_id="xyz",
            title="Test",
            authors=["Author"],
        )

        result = analyzer.evaluate_article_relevance("Test.", article)

        assert result["confidence"] == 1.0  # Should be clamped

    def test_evaluate_relevance_missing_abstract(self):
        """Test evaluation when article has no abstract."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "RELEVANT: NO\n"
            "CONFIDENCE: 0.5\n"
            "REASONING: No abstract available."
        )
        mock_llm.client.chat.completions.create.return_value = mock_response

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
        call_args = mock_llm.client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][1]["content"]
        assert "[Abstract not available]" in prompt
