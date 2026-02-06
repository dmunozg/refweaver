"""Sentence analysis pipeline for RefWeaver.

Analyzes sentences from manuscript paragraphs to determine if they need references.
"""

from typing import List

from loguru import logger

from refweaver.llm import LLMClient
from refweaver.models import Sentence
from refweaver.text_utils import split_sentences


class SentenceAnalyzer:
    """Analyzes sentences to determine if they need references."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize the sentence analyzer.

        Args:
            llm_client: LLM client for analysis. If None, creates a new instance.
        """
        self.llm = llm_client or LLMClient()
        logger.info("SentenceAnalyzer initialized")

    def analyze_paragraph(self, paragraph: str) -> List[Sentence]:
        """Analyze all sentences in a paragraph.

        Args:
            paragraph: Paragraph text to analyze.

        Returns:
            List of Sentence objects with reference analysis.
        """
        sentences = split_sentences(paragraph)
        results: List[Sentence] = []

        for sent_text in sentences:
            analysis = self.llm.analyze_sentence_needs_reference(
                sentence=sent_text,
                context=paragraph,
            )
            sentence = Sentence(
                text=sent_text,
                needs_reference=bool(analysis["needs_reference"]),
                reason=str(analysis["reason"]),
            )
            results.append(sentence)
            logger.debug(
                f"Analyzed: '{sent_text[:50]}...' -> "
                f"needs_reference={sentence.needs_reference}"
            )

        logger.info(f"Analyzed {len(results)} sentences in paragraph")
        return results

    def analyze_sentences(self, text: str) -> List[Sentence]:
        """Analyze all sentences in a text (paragraphs are processed together).

        This is a convenience method that splits text into paragraphs,
        then analyzes all sentences across all paragraphs.

        Args:
            text: Full text to analyze (can be multiple paragraphs).

        Returns:
            List of Sentence objects with reference analysis.
        """
        from refweaver.text_utils import split_paragraphs

        paragraphs = split_paragraphs(text)
        all_sentences: List[Sentence] = []

        for para in paragraphs:
            sentences = self.analyze_paragraph(para)
            all_sentences.extend(sentences)

        logger.info(f"Analyzed {len(all_sentences)} sentences total")
        return all_sentences
