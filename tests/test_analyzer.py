"""Tests for sentence analysis pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from refweaver.analyzer import SentenceAnalyzer
from refweaver.models import Sentence


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
