"""Tests for workflow helpers."""

from unittest.mock import MagicMock

from refweaver.adapters.perplexity import PerplexityAdapter
from refweaver.analyzer import SentenceAnalyzer
from refweaver.enrich import ArticleEnricher
from refweaver.evaluation_models import FinalVerdict, SentenceEvaluation
from refweaver.models import Article, Sentence
from refweaver.search import UnifiedSearch
from refweaver.workflows import analyze_paragraph_with_evidence
from tests.fixtures.sample_texts import SHORT_SAMPLE


def _make_article(external_id: str, title: str) -> Article:
    return Article(
        source="test",
        external_id=external_id,
        title=title,
        authors=["Test Author"],
        year=2024,
        abstract="Test abstract",
    )


def _make_evaluation(sentence: str, article: Article) -> SentenceEvaluation:
    return SentenceEvaluation(
        sentence=sentence,
        article=article,
        article_title=article.title,
        article_doi=article.doi,
        article_authors=article.authors,
        article_year=article.year,
        relevance_score=0.8,
        relevance_reasoning="Relevant to the claim.",
        is_relevant=True,
        stance="SUPPORTS",
        stance_confidence=0.85,
        stance_reasoning="Supports the sentence.",
        supporting_evidence="Evidence excerpt.",
        suggested_modification=None,
    )


def _make_verdict(primary_source: str) -> FinalVerdict:
    return FinalVerdict(
        overall_assessment="WELL_SUPPORTED",
        confidence=0.85,
        primary_sources=[primary_source],
        primary_source_identifiers=[],
        synthesis="Evidence supports the claim.",
        suggested_citation=None,
        suggested_rewording=None,
    )


def test_analyze_paragraph_with_evidence_short_sample_workflow():
    analyzer = MagicMock(spec=SentenceAnalyzer)
    searcher = MagicMock(spec=UnifiedSearch)
    perplexity_adapter = MagicMock(spec=PerplexityAdapter)
    enricher = MagicMock(spec=ArticleEnricher)

    sentences = [
        Sentence(
            text="Climate change has accelerated glacier retreat globally.",
            sentence_with_context="Climate change has accelerated glacier retreat globally.",
            needs_reference=True,
            reason="Specific claim",
        ),
        Sentence(
            text="The Greenland ice sheet lost approximately 280 gigatons of mass per year between 2002 and 2016.",
            sentence_with_context=(
                "The Greenland ice sheet lost approximately 280 gigatons of mass per year "
                "between 2002 and 2016."
            ),
            needs_reference=True,
            reason="Specific statistic",
        ),
        Sentence(
            text="Sea levels have been falling steadily for decades.",
            sentence_with_context="Sea levels have been falling steadily for decades.",
            needs_reference=False,
            reason="General statement",
        ),
    ]

    analyzer.analyze_paragraph.return_value = sentences
    analyzer.generate_search_keywords.side_effect = [
        ["glacier retreat", "climate change"],
        ["Greenland ice sheet mass loss"],
    ]

    article_a = _make_article("a1", "Glacier retreat observations")
    article_b = _make_article("a2", "Climate change impacts on glaciers")
    article_c = _make_article("a3", "Greenland ice sheet mass balance")
    article_p1 = _make_article("p1", "Global glacier retreat synthesis")
    article_p2 = _make_article("p2", "Greenland mass loss review")

    searcher.search.side_effect = [
        [article_a],
        [article_b],
        [article_c],
    ]
    perplexity_adapter.search.side_effect = [
        [article_p1],
        [article_p2],
    ]
    enricher.batch_enrich.side_effect = lambda articles: list(articles)

    evaluations_one = [_make_evaluation(sentences[0].text, article_a)]
    evaluations_two = [_make_evaluation(sentences[1].text, article_c)]
    analyzer.evaluate_articles.side_effect = [evaluations_one, evaluations_two]
    analyzer.synthesize_verdict.side_effect = [
        _make_verdict(article_a.title),
        _make_verdict(article_c.title),
    ]

    results = analyze_paragraph_with_evidence(
        SHORT_SAMPLE,
        analyzer=analyzer,
        searcher=searcher,
        perplexity_adapter=perplexity_adapter,
        enricher=enricher,
    )

    assert len(results) == 2
    assert results[0][0] == sentences[0]
    assert results[1][0] == sentences[1]
    assert results[0][1].overall_assessment == "WELL_SUPPORTED"
    assert results[1][1].overall_assessment == "WELL_SUPPORTED"
    assert results[0][2] == evaluations_one
    assert results[1][2] == evaluations_two

    analyzer.analyze_paragraph.assert_called_once_with(SHORT_SAMPLE)
    analyzer.generate_search_keywords.assert_any_call(sentences[0])
    analyzer.generate_search_keywords.assert_any_call(sentences[1])
    assert searcher.search.call_count == 3
    searcher.search.assert_any_call("glacier retreat", limit_per_source=5)
    searcher.search.assert_any_call("climate change", limit_per_source=5)
    searcher.search.assert_any_call("Greenland ice sheet mass loss", limit_per_source=5)
    perplexity_adapter.search.assert_any_call(sentences[0].sentence_with_context)
    perplexity_adapter.search.assert_any_call(sentences[1].sentence_with_context)
    assert enricher.batch_enrich.call_count == 2

    analyzer.evaluate_articles.assert_any_call(
        sentences[0],
        [article_a, article_b, article_p1],
        relevance_threshold=0.5,
        max_articles_for_stance=10,
    )
    analyzer.evaluate_articles.assert_any_call(
        sentences[1],
        [article_c, article_p2],
        relevance_threshold=0.5,
        max_articles_for_stance=10,
    )
    analyzer.synthesize_verdict.assert_any_call(sentences[0], evaluations_one)
    analyzer.synthesize_verdict.assert_any_call(sentences[1], evaluations_two)
