"""Tests for text processing utilities."""

from refweaver.text_utils import (
    preprocess_manuscript,
    split_paragraphs,
    split_sentences,
)
from tests.fixtures.sample_texts import (
    MULTIPLE_PARAGRAPH_SAMPLE,
    SAMPLE_INTRODUCTION,
    SHORT_SAMPLE,
    TRICKY_SAMPLE,
)


class TestSplitParagraphs:
    """Test suite for paragraph splitting."""

    def test_basic_split(self):
        """Test basic paragraph splitting."""
        text = "First paragraph.\n\nSecond paragraph."
        result = split_paragraphs(text)
        assert len(result) == 2
        assert result[0] == "First paragraph."
        assert result[1] == "Second paragraph."

    def test_multiple_blank_lines(self):
        """Test handling of multiple blank lines."""
        text = "Para one.\n\n\n\nPara two."
        result = split_paragraphs(text)
        assert len(result) == 2

    def test_whitespace_only_paragraphs_filtered(self):
        """Test that whitespace-only paragraphs are filtered out."""
        text = "Para one.\n\n   \n\nPara two."
        result = split_paragraphs(text)
        assert len(result) == 2

    def test_leading_trailing_whitespace_stripped(self):
        """Test that leading/trailing whitespace is stripped."""
        text = "  First para.  \n\n  Second para.  "
        result = split_paragraphs(text)
        assert result[0] == "First para."
        assert result[1] == "Second para."

    def test_single_paragraph(self):
        """Test single paragraph without splits."""
        text = "Just one paragraph."
        result = split_paragraphs(text)
        assert len(result) == 1
        assert result[0] == "Just one paragraph."

    def test_empty_string(self):
        """Test empty string handling."""
        result = split_paragraphs("")
        assert result == []

    def test_whitespace_only_string(self):
        """Test whitespace-only string handling."""
        result = split_paragraphs("   \n\n   ")
        assert result == []

    def test_sample_introduction(self):
        """Test splitting the sample introduction."""
        result = split_paragraphs(SAMPLE_INTRODUCTION)
        # SAMPLE_INTRODUCTION is a single paragraph
        assert len(result) == 1
        assert "LRLLR cell-penetrating motif" in result[0]
        assert "smacN peptide" in result[0]
        assert "graphene oxide" in result[0]

    def test_multiple_paragraph_sample(self):
        """Test splitting the multiple paragraph sample."""
        result = split_paragraphs(MULTIPLE_PARAGRAPH_SAMPLE)
        assert len(result) == 2
        # First paragraph - introduction about LRLLR motif
        assert "Cell-penetrating peptides" in result[0]
        assert "LRLLR motif" in result[0]
        assert "smacN" in result[0]
        assert "NR2B9c" in result[0]
        # Second paragraph - results/discussion
        assert "Potential of mean force" in result[1]
        assert "POPC/POPG bilayer" in result[1]
        assert "hydrogen bonding" in result[1]

    def test_multiple_paragraph_sample_structure(self):
        """Test the structural integrity of multi-paragraph splitting."""
        result = split_paragraphs(MULTIPLE_PARAGRAPH_SAMPLE)
        # Each paragraph should be non-empty and properly stripped
        for para in result:
            assert len(para) > 0
            assert para == para.strip()
        # Should have exactly 2 paragraphs separated by blank lines
        assert result[0].endswith("ischemic stroke.")
        assert result[1].startswith("Potential of mean force")


class TestSplitSentences:
    """Test suite for sentence splitting."""

    def test_basic_sentences(self):
        """Test basic sentence splitting."""
        text = "First sentence. Second sentence. Third sentence."
        result = split_sentences(text)
        assert len(result) == 3
        assert result[0] == "First sentence."
        assert result[1] == "Second sentence."
        assert result[2] == "Third sentence."

    def test_abbreviations_preserved(self):
        """Test that abbreviations don't break sentence detection."""
        text = "Dr. Smith visited the U.S.A. yesterday. It was sunny."
        result = split_sentences(text)
        assert len(result) == 2
        assert "Dr. Smith" in result[0]
        assert "It was sunny" in result[1]

    def test_tricky_sample(self):
        """Test the tricky sample with many edge cases."""
        result = split_sentences(TRICKY_SAMPLE)
        # Should split into ~7 sentences despite abbreviations
        assert len(result) >= 6
        # Check that abbreviations don't cause false splits
        full_text = " ".join(result)
        assert "Dr. Johnson" in full_text
        assert "D.C." in full_text
        assert "Jan. 15" in full_text
        assert "p.m." in full_text
        assert "Ph.D." in full_text
        assert "U.S.A." in full_text
        assert "i.e." in full_text

    def test_short_sample(self):
        """Test sentence splitting on the short sample."""
        result = split_sentences(SHORT_SAMPLE)
        assert len(result) == 4
        assert "Climate change" in result[0]
        assert "Greenland ice sheet" in result[1]
        assert "1,000 years" in result[2]
        assert "Rising sea levels" in result[3]


class TestPreprocessManuscript:
    """Test suite for full manuscript preprocessing."""

    def test_full_pipeline(self):
        """Test the complete preprocessing pipeline."""
        text = "Para one. Sentence two.\n\nPara two."
        result = preprocess_manuscript(text)
        assert len(result) == 2
        assert result[0] == ["Para one.", "Sentence two."]
        assert result[1] == ["Para two."]

    def test_sample_introduction_full(self):
        """Test preprocessing the full sample introduction."""
        result = preprocess_manuscript(SAMPLE_INTRODUCTION)
        assert len(result) == 1  # Single paragraph
        # Paragraph should have multiple sentences
        assert len(result[0]) >= 6
        # Check content in sentences
        assert any("LRLLR" in sent for sent in result[0])
        assert any("smacN" in sent for sent in result[0])
        assert any("graphene oxide" in sent for sent in result[0])
