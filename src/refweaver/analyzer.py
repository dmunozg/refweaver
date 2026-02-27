"""Sentence analysis pipeline for RefWeaver.

Analyzes sentences from manuscript paragraphs to determine if they need references,
generates search keywords, and evaluates article relevance using a three-stage approach:

1. Relevance scoring: Quick filter to identify potentially relevant articles
2. Stance evaluation: Detailed analysis of how relevant articles relate to the sentence
3. Final synthesis: Overall verdict based on all evidence
"""

from typing import TYPE_CHECKING, cast

from loguru import logger

from refweaver.evaluation_models import SentenceEvaluation
from refweaver.llm import LLMClient
from refweaver.models import Article, Sentence
from refweaver.text_utils import split_sentences

if TYPE_CHECKING:
    from refweaver.evaluation_models import FinalVerdict


DEFAULT_RELEVANCE_THRESHOLD = 0.5
DEFAULT_MAX_ARTICLES_FOR_STANCE = 10


class SentenceAnalyzer:
    """Analyzes sentences to determine if they need references and evaluates supporting evidence."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize the sentence analyzer.

        Args:
            llm_client: LLM client for analysis. If None, creates a new instance.
        """
        self.llm = llm_client or LLMClient()
        logger.info("SentenceAnalyzer initialized")

    def analyze_paragraph(self, paragraph: str) -> list[Sentence]:
        """Analyze all sentences in a paragraph.

        Args:
            paragraph: Paragraph text to analyze.

        Returns:
            List of Sentence objects with reference analysis.
        """
        sentences = split_sentences(paragraph)
        results: list[Sentence] = []

        for sent_text in sentences:
            analysis = self.llm.analyze_sentence_needs_reference(
                sentence=sent_text,
                context=paragraph,
            )
            rewritten_sentence = None
            rewrite_applied = False
            if bool(analysis["needs_reference"]):
                rewritten_sentence = self.llm.rewrite_sentence_with_context(
                    sentence=sent_text,
                    context=paragraph,
                )
                rewrite_applied = rewritten_sentence != sent_text
            sentence = Sentence(
                text=sent_text,
                sentence_with_context=rewritten_sentence,
                rewrite_applied=rewrite_applied,
                needs_reference=bool(analysis["needs_reference"]),
                reason=str(analysis["reason"]),
            )
            results.append(sentence)
            logger.debug(
                f"Analyzed: '{sent_text[:50]}...' -> needs_reference={sentence.needs_reference}"
            )

        logger.info(f"Analyzed {len(results)} sentences in paragraph")
        return results

    def analyze_sentences(self, text: str) -> list[Sentence]:
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
        all_sentences: list[Sentence] = []

        for para in paragraphs:
            sentences = self.analyze_paragraph(para)
            all_sentences.extend(sentences)

        logger.info(f"Analyzed {len(all_sentences)} sentences total")
        return all_sentences

    def generate_search_keywords(
        self,
        sentence: str | Sentence,
    ) -> list[str]:
        """Generate search keywords for finding supporting articles.

        Uses LLM with structured output to extract key concepts and terms
        from a sentence for effective academic search queries.

        Args:
            sentence: The sentence needing reference support (str or Sentence object).

        Returns:
            List of search keyword strings optimized for academic search.
        """
        # Extract text if Sentence object is passed
        if isinstance(sentence, Sentence):
            sentence_text = sentence.sentence_with_context or sentence.text
        else:
            sentence_text = sentence

        # Delegate to LLM client which uses pydantic-ai structured output
        return self.llm.generate_search_keywords(sentence_text)

    def evaluate_article_relevance(
        self,
        sentence: str | Sentence,
        article: Article,
    ) -> dict[str, str | float | None]:
        """Evaluate how an article relates to a sentence using the abstract.

        Args:
            sentence: The claim to evaluate (str or Sentence object).
            article: Article metadata for evaluation.

        Returns:
            Dict with verdict, confidence, reasoning, and suggested modification.
        """
        if isinstance(sentence, Sentence):
            sentence_text = sentence.sentence_with_context or sentence.text
        else:
            sentence_text = sentence
        return self.llm.evaluate_article_relevance(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            article_abstract=article.abstract,
        )

    def evaluate_article_with_landing_page(
        self,
        sentence: str | Sentence,
        article: Article,
        timeout: int = 30,
    ) -> dict[str, str | float | None]:
        """Evaluate using abstract first, optionally falling back to landing page.

        Returns evaluation dict including an `evaluation_source` key.
        """
        if isinstance(sentence, Sentence):
            sentence_text = sentence.sentence_with_context or sentence.text
        else:
            sentence_text = sentence
        abstract_result = self.llm.evaluate_article_relevance(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            article_abstract=article.abstract,
        )
        evaluation_source = "abstract"

        if article.open_access and abstract_result.get("verdict") in {
            "INSUFFICIENT_INFO",
            "PARTIALLY_SUPPORTS",
        }:
            from refweaver.web_fetch import fetch_article_landing_page

            landing_text = fetch_article_landing_page(article, timeout=timeout)
            if landing_text and abstract_result.get("verdict") in {
                "INSUFFICIENT_INFO",
                "PARTIALLY_SUPPORTS",
            }:
                fulltext_result = self.llm.evaluate_article_relevance_fulltext(
                    sentence=sentence_text,
                    article_title=article.title,
                    article_authors=article.authors,
                    article_year=article.year,
                    fulltext_content=landing_text,
                )
                fulltext_result["evaluation_source"] = "fulltext"
                return fulltext_result

        abstract_result["evaluation_source"] = evaluation_source
        return abstract_result

    def evaluate_articles(
        self,
        sentence: str | Sentence,
        articles: list[Article],
        relevance_threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
        max_articles_for_stance: int = DEFAULT_MAX_ARTICLES_FOR_STANCE,
    ) -> list[SentenceEvaluation]:
        """Evaluate all articles for a sentence using three-stage pipeline.

        Stage 1: Score relevance for all articles (quick filter)
        Stage 2: Detailed stance evaluation for relevant articles
        Stage 3: Collect into SentenceEvaluation objects

        Args:
            sentence: The sentence/claim to evaluate.
            articles: List of candidate articles to evaluate.
            relevance_threshold: Minimum score (0-1) to pass to stage 2.
            max_articles_for_stance: Max articles to evaluate in detail (by relevance score).

        Returns:
            List of SentenceEvaluation objects, sorted by combined score.
        """
        if isinstance(sentence, Sentence):
            sentence_text = sentence.sentence_with_context or sentence.text
        else:
            sentence_text = sentence

        logger.info(f"Evaluating {len(articles)} articles for: {sentence_text[:60]}...")

        # Stage 1: Relevance scoring for all articles
        logger.debug("Stage 1: Scoring relevance for all articles...")
        evaluations: list[SentenceEvaluation] = []

        for article in articles:
            score_result = self.llm.score_article_relevance(
                sentence=sentence_text,
                article_title=article.title,
                article_abstract=article.abstract,
            )

            evaluation = SentenceEvaluation(
                sentence=sentence_text,
                article=article,
                article_title=article.title,
                article_doi=article.doi,
                article_authors=article.authors,
                article_year=article.year,
                relevance_score=score_result["score"],
                relevance_reasoning=score_result["reasoning"],
                is_relevant=score_result["score"] >= relevance_threshold,
            )
            evaluations.append(evaluation)

        # Sort by relevance score descending
        evaluations.sort(key=lambda e: e.relevance_score, reverse=True)

        relevant_count = sum(1 for e in evaluations if e.is_relevant)
        logger.info(
            f"Stage 1 complete: {relevant_count}/{len(articles)} articles above "
            f"threshold ({relevance_threshold})"
        )

        # Stage 2: Detailed stance evaluation for relevant articles (top N)
        relevant_evaluations = [e for e in evaluations if e.is_relevant]
        articles_for_stance = relevant_evaluations[:max_articles_for_stance]

        logger.debug(
            f"Stage 2: Detailed stance evaluation for {len(articles_for_stance)} articles..."
        )

        for evaluation in articles_for_stance:
            # Get the article directly from the evaluation
            article = cast(Article, evaluation.article)

            fulltext_content: str | None = None
            if article.open_access:
                from refweaver.pdf_extract import try_get_fulltext_from_pdf
                from refweaver.web_fetch import fetch_article_landing_page

                fulltext_content = try_get_fulltext_from_pdf(
                    article,
                    try_alternative_sources=False,
                )
                if not fulltext_content:
                    fulltext_content = fetch_article_landing_page(article)

            if fulltext_content:
                logger.debug(f"Using full text for stance evaluation: {article.title[:50]}...")
            else:
                logger.debug(
                    f"Falling back to abstract for stance evaluation: {article.title[:50]}..."
                )

            stance_result = self.llm.evaluate_article_stance(
                sentence=sentence_text,
                article_title=article.title,
                article_authors=article.authors,
                article_year=article.year,
                article_abstract=article.abstract,
                article_fulltext=fulltext_content,
            )

            # Update evaluation with stance results
            evaluation.stance = stance_result["stance"]
            evaluation.stance_confidence = stance_result["confidence"]
            evaluation.stance_reasoning = stance_result["reasoning"]
            evaluation.supporting_evidence = stance_result["evidence"]
            evaluation.suggested_modification = stance_result["modification"]

        logger.info("Stage 2 complete: Stance evaluation finished")

        # Re-sort by combined score (relevance * confidence)
        evaluations.sort(key=lambda e: e.combined_score, reverse=True)

        return evaluations

    def synthesize_verdict(
        self,
        sentence: str | Sentence,
        evaluations: list[SentenceEvaluation],
        min_relevant_articles: int = 1,
    ) -> "FinalVerdict":
        """Synthesize final verdict from article evaluations.

        Stage 3: Takes all evaluations and produces an overall assessment
        of whether the sentence is supported by the literature.

        Args:
            sentence: The original sentence/claim.
            evaluations: List of SentenceEvaluation objects from evaluate_articles().
            min_relevant_articles: Minimum relevant articles needed for a verdict.

        Returns:
            FinalVerdict with overall assessment and recommendations.
        """
        from refweaver.evaluation_models import FinalVerdict

        if isinstance(sentence, Sentence):
            sentence_text = sentence.sentence_with_context or sentence.text
        else:
            sentence_text = sentence

        # Filter to only relevant evaluations with stance
        relevant_with_stance = [e for e in evaluations if e.is_relevant and e.stance is not None]

        logger.info(f"Synthesizing verdict from {len(relevant_with_stance)} evaluated articles")

        # Check if we have enough evidence
        if len(relevant_with_stance) < min_relevant_articles:
            logger.warning(
                f"Insufficient evidence: {len(relevant_with_stance)} relevant articles, "
                f"need {min_relevant_articles}"
            )
            return FinalVerdict(
                overall_assessment="INSUFFICIENT_EVIDENCE",
                confidence=0.0,
                synthesis=f"Only {len(relevant_with_stance)} relevant articles found. "
                f"Need at least {min_relevant_articles} for a reliable verdict.",
                suggested_citation=None,
                suggested_rewording=None,
            )

        # Prepare evaluation data for LLM (include index for matching back)
        eval_data = []
        for idx, ev in enumerate(relevant_with_stance):
            eval_data.append(
                {
                    "index": idx,
                    "title": ev.article_title,
                    "doi": ev.article_doi,
                    "stance": ev.stance,
                    "confidence": ev.stance_confidence or 0.0,
                    "reasoning": ev.stance_reasoning or "",
                    "evidence": ev.supporting_evidence,
                }
            )

        # Get LLM synthesis
        synthesis_result = self.llm.synthesize_final_verdict(
            sentence=sentence_text,
            evaluations=eval_data,
        )

        # Map LLM output to FinalVerdict
        verdict_mapping = {
            "WELL_SUPPORTED": "WELL_SUPPORTED",
            "PARTIALLY_SUPPORTED": "PARTIALLY_SUPPORTED",
            "CONTRADICTED": "CONTRADICTED",
            "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
            "NOT_SUPPORTED": "NOT_SUPPORTED",
        }

        # Build primary_source_identifiers from LLM output
        from refweaver.evaluation_models import SourceIdentifier

        primary_source_identifiers: list[SourceIdentifier] = []
        for source_title in synthesis_result.get("primary_sources", []):
            # Find matching evaluation by title
            for idx, ev in enumerate(relevant_with_stance):
                if ev.article_title == source_title or source_title in ev.article_title:
                    primary_source_identifiers.append(
                        SourceIdentifier(
                            title=ev.article_title,
                            doi=ev.article_doi,
                            index=idx,
                        )
                    )
                    break

        final_verdict = FinalVerdict(
            overall_assessment=verdict_mapping.get(
                synthesis_result["verdict"], "INSUFFICIENT_EVIDENCE"
            ),
            confidence=synthesis_result["confidence"],
            primary_sources=synthesis_result["primary_sources"],
            primary_source_identifiers=primary_source_identifiers,
            synthesis=synthesis_result["synthesis"],
            suggested_citation=synthesis_result["citation_suggestion"],
            suggested_rewording=synthesis_result["rewording_suggestion"],
        )

        logger.success(
            f"Final verdict: {final_verdict.overall_assessment} "
            f"(confidence: {final_verdict.confidence:.2f})"
        )

        return final_verdict

    def analyze_sentence_with_articles(
        self,
        sentence: str | Sentence,
        articles: list[Article],
        relevance_threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
        max_articles_for_stance: int = DEFAULT_MAX_ARTICLES_FOR_STANCE,
        min_relevant_articles: int = 1,
    ) -> tuple[list[SentenceEvaluation], "FinalVerdict"]:
        """Complete analysis pipeline: evaluate articles and synthesize verdict.

        Convenience method that runs the full three-stage pipeline:
        1. Evaluate all articles for relevance and stance
        2. Synthesize final verdict

        Args:
            sentence: The sentence/claim to analyze.
            articles: List of candidate articles.
            relevance_threshold: Minimum relevance score to pass to stance evaluation.
            max_articles_for_stance: Max articles for detailed stance evaluation.
            min_relevant_articles: Minimum articles needed for a verdict.

        Returns:
            Tuple of (list of SentenceEvaluation, FinalVerdict).
        """
        # Stage 1 & 2: Evaluate all articles
        evaluations = self.evaluate_articles(
            sentence=sentence,
            articles=articles,
            relevance_threshold=relevance_threshold,
            max_articles_for_stance=max_articles_for_stance,
        )

        # Stage 3: Synthesize verdict
        verdict = self.synthesize_verdict(
            sentence=sentence,
            evaluations=evaluations,
            min_relevant_articles=min_relevant_articles,
        )

        return evaluations, verdict
