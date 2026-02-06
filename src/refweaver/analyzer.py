"""Sentence analysis pipeline for RefWeaver.

Analyzes sentences from manuscript paragraphs to determine if they need references,
generates search keywords, and evaluates article relevance.
"""

from typing import List

from loguru import logger

from refweaver.llm import LLMClient
from refweaver.models import Article, Sentence
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

    def generate_search_keywords(self, sentence: str | Sentence) -> list[str]:
        """Generate search keywords for finding supporting articles.

        Uses LLM with structured output to extract key concepts and terms
        from a sentence for effective academic search queries.

        Args:
            sentence: The sentence needing reference support (str or Sentence object).

        Returns:
            List of search keyword strings optimized for academic search.
        """
        # Extract text if Sentence object is passed
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        # Delegate to LLM client which uses pydantic-ai structured output
        return self.llm.generate_search_keywords(sentence_text)

    async def generate_search_keywords_async(self, sentence: str | Sentence) -> list[str]:
        """Async version of generate_search_keywords."""
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence
        return await self.llm.generate_search_keywords_async(sentence_text)

    def evaluate_article_relevance(
        self,
        sentence: str | Sentence,
        article: Article,
    ) -> dict[str, bool | str | float]:
        """Evaluate if an article is relevant to support a sentence.

        Uses LLM with structured output to compare the sentence's claim
        against the article's metadata to determine relevance.

        Args:
            sentence: The claim needing support (str or Sentence object).
            article: The candidate article to evaluate.

        Returns:
            Dict with 'relevant' (bool), 'confidence' (float 0-1),
            and 'reasoning' (str) explaining the decision.
        """
        # Extract text if Sentence object is passed
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        # Delegate to LLM client which uses pydantic-ai structured output
        return self.llm.evaluate_article_relevance(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            article_abstract=article.abstract,
        )

    async def evaluate_article_relevance_async(
        self,
        sentence: str | Sentence,
        article: Article,
    ) -> dict[str, bool | str | float]:
        """Async version of evaluate_article_relevance."""
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        return await self.llm.evaluate_article_relevance_async(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            article_abstract=article.abstract,
        )
