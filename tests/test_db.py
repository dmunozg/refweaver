"""DB persistence tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from refweaver.db.models import (
    ArticleRecord,
    Base,
    EvaluationRecord,
    Run,
    SentenceRecord,
    User,
    VerdictRecord,
)
from refweaver.db.persist import create_queued_run, persist_run_results
from refweaver.evaluation_models import FinalVerdict, SentenceEvaluation, SourceIdentifier
from pydantic import HttpUrl

from refweaver.models import Article, Sentence


def _make_session() -> tuple[Session, Engine]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine), engine


def test_create_all_models_directly() -> None:
    session, engine = _make_session()
    user = User(
        id="user-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    run = Run(
        id="run-1",
        user_id=user.id,
        mode="paragraph",
        status="completed",
        input_text="Example",
        config={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    sentence = SentenceRecord(
        id="sentence-1",
        run_id=run.id,
        text="A sentence.",
        sentence_with_context="A sentence.",
        rewrite_applied=False,
        needs_reference=True,
        reason="Test",
    )
    article = ArticleRecord(
        id="openalex:123",
        source="openalex",
        external_id="123",
        title="Test Article",
        authors=["Author"],
        year=2024,
        doi="10.1000/test",
        url="https://example.com",
        abstract="Abstract",
    )
    evaluation = EvaluationRecord(
        id="evaluation-1",
        sentence_id=sentence.id,
        article_id=article.id,
        relevance_score=0.8,
        relevance_reasoning="Relevant",
        is_relevant=True,
        stance="SUPPORTS",
        stance_confidence=0.9,
        stance_reasoning="Supports",
        supporting_evidence="Evidence",
        suggested_modification=None,
    )
    verdict = VerdictRecord(
        id="verdict-1",
        sentence_id=sentence.id,
        overall_assessment="WELL_SUPPORTED",
        confidence=0.9,
        primary_sources=["Test Article"],
        primary_source_identifiers=[{"title": "Test Article", "doi": "10.1000/test", "index": 0}],
        synthesis="Synthesis",
        suggested_citation=None,
        suggested_rewording=None,
    )
    session.add_all([user, run, sentence, article, evaluation, verdict])
    session.commit()

    assert session.get(User, user.id) is not None
    assert session.get(Run, run.id) is not None
    assert session.get(SentenceRecord, sentence.id) is not None
    assert session.get(ArticleRecord, article.id) is not None
    assert session.get(EvaluationRecord, evaluation.id) is not None
    assert session.get(VerdictRecord, verdict.id) is not None
    session.close()
    engine.dispose()


def test_persist_run_results_creates_records() -> None:
    session, engine = _make_session()
    sentence = Sentence(
        text="Example sentence.",
        sentence_with_context="Example sentence.",
        rewrite_applied=False,
        needs_reference=True,
        reason="Test",
    )
    article = Article(
        source="openalex",
        external_id="oa-1",
        title="Example Article",
        authors=["Researcher"],
        year=2023,
        doi="10.1000/example",
        url=HttpUrl("https://example.org"),
        abstract="Abstract",
    )
    evaluation = SentenceEvaluation(
        sentence=sentence.text,
        article=article,
        article_title=article.title,
        article_doi=article.doi,
        article_authors=article.authors,
        article_year=article.year,
        relevance_score=0.9,
        relevance_reasoning="Relevant",
        is_relevant=True,
        stance="SUPPORTS",
        stance_confidence=0.95,
        stance_reasoning="Supports",
        supporting_evidence="Evidence",
        suggested_modification=None,
    )
    verdict = FinalVerdict(
        overall_assessment="WELL_SUPPORTED",
        confidence=0.9,
        primary_sources=[article.title],
        primary_source_identifiers=[
            SourceIdentifier(title=article.title, doi=article.doi, index=0)
        ],
        synthesis="Synthesis",
        suggested_citation=None,
        suggested_rewording=None,
    )
    results = [(sentence, verdict, [evaluation])]

    run_id = uuid4().hex
    persist_run_results(
        session,
        run_id=run_id,
        user_id="user-2",
        mode="paragraph",
        input_text="Example sentence.",
        results=results,
    )

    assert session.get(Run, run_id) is not None
    assert session.query(SentenceRecord).filter_by(run_id=run_id).count() == 1
    assert session.query(ArticleRecord).filter_by(external_id="oa-1").count() == 1
    assert session.query(EvaluationRecord).count() == 1
    assert session.query(VerdictRecord).count() == 1
    session.close()
    engine.dispose()


def test_create_queued_run_idempotent() -> None:
    session, engine = _make_session()
    run = create_queued_run(
        session,
        run_id="run-queued",
        user_id="user-queued",
        mode="paragraph",
        input_text="Example",
    )
    assert run.status == "queued"
    run2 = create_queued_run(
        session,
        run_id="run-queued",
        user_id="user-queued",
        mode="paragraph",
        input_text="Example",
    )
    assert run2.id == run.id
    session.close()
    engine.dispose()
