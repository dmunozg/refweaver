"""Shared reporting helpers."""

from pydantic import HttpUrl

from refweaver.db.models import ArticleRecord, EvaluationRecord, SentenceRecord, VerdictRecord
from refweaver.evaluation_models import FinalVerdict, SentenceEvaluation, SourceIdentifier
from refweaver.formatting import sentence_evaluations_to_markdown
from refweaver.models import Article, Sentence


def build_run_report(
    run_id: str,
    sentences: list[SentenceRecord],
    verdicts: dict[str, VerdictRecord],
    evaluations: list[EvaluationRecord] | None = None,
    articles: dict[str, ArticleRecord] | None = None,
) -> str:
    """Build a markdown report for a run."""
    if evaluations is None:
        report_lines = [f"# Run {run_id}"]
        for sentence in sentences:
            verdict = verdicts.get(sentence.id)
            report_lines.append(f"- {sentence.text}")
            if verdict:
                report_lines.append(f"  - Verdict: {verdict.overall_assessment}")
        return "\n".join(report_lines)

    evaluations_by_sentence: dict[str, list[EvaluationRecord]] = {}
    for evaluation in evaluations:
        evaluations_by_sentence.setdefault(evaluation.sentence_id, []).append(evaluation)

    articles_by_id = articles or {}

    results: list[tuple[Sentence, FinalVerdict, list[SentenceEvaluation]]] = []
    for sentence in sentences:
        sentence_model = Sentence(
            text=sentence.text,
            sentence_with_context=sentence.sentence_with_context,
            rewrite_applied=sentence.rewrite_applied,
            needs_reference=sentence.needs_reference,
            reason=sentence.reason,
        )
        verdict = verdicts.get(sentence.id)
        if verdict is None:
            continue

        verdict_model = FinalVerdict(
            overall_assessment=verdict.overall_assessment,
            confidence=verdict.confidence,
            primary_sources=verdict.primary_sources,
            primary_source_identifiers=[
                SourceIdentifier.model_validate(identifier)
                for identifier in verdict.primary_source_identifiers
            ],
            synthesis=verdict.synthesis,
            suggested_citation=verdict.suggested_citation,
            suggested_rewording=verdict.suggested_rewording,
        )
        evaluation_models: list[SentenceEvaluation] = []
        for evaluation in evaluations_by_sentence.get(sentence.id, []):
            article_record = articles_by_id.get(evaluation.article_id)
            if article_record is None:
                article = Article(
                    source="unknown",
                    external_id=evaluation.article_id,
                    title="",
                    authors=[],
                    year=None,
                    doi=None,
                    url=None,
                    abstract=None,
                )
            else:
                url = HttpUrl(article_record.url) if article_record.url else None
                article = Article(
                    source=article_record.source,
                    external_id=article_record.external_id,
                    title=article_record.title,
                    authors=article_record.authors,
                    year=article_record.year,
                    doi=article_record.doi,
                    url=url,
                    abstract=article_record.abstract,
                )
            evaluation_models.append(
                SentenceEvaluation(
                    sentence=sentence.text,
                    article=article,
                    article_title=article.title,
                    article_doi=article.doi,
                    article_authors=article.authors,
                    article_year=article.year,
                    relevance_score=evaluation.relevance_score or 0.0,
                    relevance_reasoning=evaluation.relevance_reasoning or "",
                    is_relevant=evaluation.is_relevant,
                    stance=evaluation.stance,
                    stance_confidence=evaluation.stance_confidence,
                    stance_reasoning=evaluation.stance_reasoning,
                    supporting_evidence=evaluation.supporting_evidence,
                    suggested_modification=evaluation.suggested_modification,
                )
            )
        results.append((sentence_model, verdict_model, evaluation_models))

    return sentence_evaluations_to_markdown(results)
