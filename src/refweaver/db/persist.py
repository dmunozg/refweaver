"""Persistence helpers for analysis runs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from refweaver.db.models import (
    ArticleRecord,
    EvaluationRecord,
    Run,
    SentenceRecord,
    User,
    VerdictRecord,
)
from refweaver.evaluation_models import FinalVerdict, SentenceEvaluation
from refweaver.models import Article, Sentence


def _get_or_create_user(session: Session, user_id: str) -> User:
    user = session.get(User, user_id)
    if user is None:
        user = User(id=user_id)
        session.add(user)
    return user


def create_queued_run(
    session: Session,
    *,
    run_id: str,
    user_id: str,
    mode: str = "paragraph",
    input_text: str,
) -> Run:
    """Create a queued run entry if it does not already exist."""
    _get_or_create_user(session, user_id)
    existing = session.get(Run, run_id)
    if existing is not None:
        return existing

    now = datetime.now(UTC)
    run = Run(
        id=run_id,
        user_id=user_id,
        mode=mode,
        status="queued",
        input_text=input_text,
        config={},
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    session.commit()
    return run


def _get_or_create_article(session: Session, evaluation: SentenceEvaluation) -> ArticleRecord:
    article_obj = evaluation.article
    if not isinstance(article_obj, Article):
        raise ValueError("Evaluation article must be an Article")
    key = f"{article_obj.source}:{article_obj.external_id}"
    existing = session.get(ArticleRecord, key)
    if existing is not None:
        return existing

    record = ArticleRecord(
        id=key,
        source=article_obj.source,
        external_id=article_obj.external_id,
        title=article_obj.title,
        authors=article_obj.authors,
        year=article_obj.year,
        doi=article_obj.doi,
        url=str(article_obj.url) if article_obj.url else None,
        abstract=article_obj.abstract,
    )
    session.add(record)
    return record


def persist_run_results(
    session: Session,
    *,
    run_id: str,
    user_id: str,
    mode: str,
    input_text: str,
    results: Sequence[tuple[Sentence | str, FinalVerdict, list[SentenceEvaluation]]],
) -> Run:
    """Persist run results and return the Run record."""
    _get_or_create_user(session, user_id)
    now = datetime.now(UTC)
    run = session.get(Run, run_id)
    if run is None:
        run = Run(
            id=run_id,
            user_id=user_id,
            mode=mode,
            status="completed",
            input_text=input_text,
            config={},
            created_at=now,
            updated_at=now,
        )
        session.add(run)
    else:
        run.status = "completed"
        run.updated_at = now

    for sentence_obj, verdict, evaluations in results:
        if isinstance(sentence_obj, Sentence):
            sentence_text = sentence_obj.text
            sentence_with_context = sentence_obj.sentence_with_context
            rewrite_applied = sentence_obj.rewrite_applied
            needs_reference = sentence_obj.needs_reference
            reason = sentence_obj.reason
        else:
            sentence_text = str(sentence_obj)
            sentence_with_context = None
            rewrite_applied = False
            needs_reference = False
            reason = ""

        sentence_record = SentenceRecord(
            id=uuid4().hex,
            run_id=run_id,
            text=sentence_text,
            sentence_with_context=sentence_with_context,
            rewrite_applied=rewrite_applied,
            needs_reference=needs_reference,
            reason=reason,
        )
        session.add(sentence_record)

        for evaluation in evaluations:
            article_record = _get_or_create_article(session, evaluation)
            evaluation_record = EvaluationRecord(
                id=uuid4().hex,
                sentence_id=sentence_record.id,
                article_id=article_record.id,
                relevance_score=evaluation.relevance_score,
                relevance_reasoning=evaluation.relevance_reasoning,
                is_relevant=evaluation.is_relevant,
                stance=evaluation.stance,
                stance_confidence=evaluation.stance_confidence,
                stance_reasoning=evaluation.stance_reasoning,
                supporting_evidence=evaluation.supporting_evidence,
                suggested_modification=evaluation.suggested_modification,
            )
            session.add(evaluation_record)

        verdict_record = VerdictRecord(
            id=uuid4().hex,
            sentence_id=sentence_record.id,
            overall_assessment=verdict.overall_assessment,
            confidence=verdict.confidence,
            primary_sources=verdict.primary_sources,
            primary_source_identifiers=[
                identifier.model_dump(mode="json")
                for identifier in verdict.primary_source_identifiers
            ],
            synthesis=verdict.synthesis,
            suggested_citation=verdict.suggested_citation,
            suggested_rewording=verdict.suggested_rewording,
        )
        session.add(verdict_record)

    session.commit()
    return run
