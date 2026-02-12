"""High-level workflows for end-to-end analysis."""

from __future__ import annotations

from loguru import logger

from refweaver.adapters.perplexity import PerplexityAdapter
from refweaver.analyzer import SentenceAnalyzer
from refweaver.dedup import deduplicate_articles
from refweaver.enrich import ArticleEnricher
from refweaver.models import Sentence
from refweaver.search import UnifiedSearch


def analyze_paragraph_with_evidence(
    paragraph: str,
    *,
    analyzer: SentenceAnalyzer | None = None,
    searcher: UnifiedSearch | None = None,
    perplexity_adapter: PerplexityAdapter | None = None,
    enricher: ArticleEnricher | None = None,
    keyword_limit: int = 2,
    limit_per_source: int = 5,
    relevance_threshold: float = 0.5,
    max_articles_for_stance: int = 10,
) -> list[tuple[Sentence, object, list[object]]]:
    """Analyze a paragraph and return sentence verdicts with evaluations.

    Args:
        paragraph: Paragraph text to analyze.
        analyzer: Optional SentenceAnalyzer (creates default if None).
        searcher: Optional UnifiedSearch (creates default if None).
        perplexity_adapter: Optional PerplexityAdapter (creates default if None).
        enricher: Optional ArticleEnricher (creates default if None).
        keyword_limit: Max keywords to query per sentence.
        limit_per_source: Max results per search adapter.
        relevance_threshold: Minimum relevance score for stance evaluation.
        max_articles_for_stance: Max articles to evaluate in detail.

    Returns:
        List of (Sentence, FinalVerdict, list[SentenceEvaluation]).
    """
    analyzer = analyzer or SentenceAnalyzer()
    searcher = searcher or UnifiedSearch()
    perplexity_adapter = perplexity_adapter or PerplexityAdapter()
    enricher = enricher or ArticleEnricher()

    sentences = analyzer.analyze_paragraph(paragraph)
    results: list[tuple[Sentence, object, list[object]]] = []

    for sentence in sentences:
        if not sentence.needs_reference:
            continue

        keywords = analyzer.generate_search_keywords(sentence, context=paragraph)
        found_articles = []

        for keyword in keywords[:keyword_limit]:
            found_articles.extend(searcher.search(keyword, limit_per_source=limit_per_source))

        found_articles.extend(perplexity_adapter.search(sentence.text))

        unique_articles = deduplicate_articles(found_articles)
        enriched_articles = enricher.batch_enrich(unique_articles)
        enriched_articles = deduplicate_articles(enriched_articles)

        evaluations = analyzer.evaluate_articles(
            sentence,
            enriched_articles,
            relevance_threshold=relevance_threshold,
            max_articles_for_stance=max_articles_for_stance,
        )
        verdict = analyzer.synthesize_verdict(sentence, evaluations)
        results.append((sentence, verdict, evaluations))

    logger.info(f"Completed paragraph analysis with {len(results)} sentences needing references")
    return results
