"""Run retrieval endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from refweaver.api.dependencies import get_db_session, get_user_id, rate_limit_user, verify_api_key
from refweaver.api.errors import http_error
from refweaver.api.reporting import build_run_report
from refweaver.db.models import ArticleRecord, EvaluationRecord, Run, SentenceRecord, VerdictRecord

router = APIRouter(
    tags=["runs"],
    dependencies=[Depends(verify_api_key), Depends(rate_limit_user)],
)


def _serialize_run(run: Run) -> dict[str, object]:
    return {
        "id": run.id,
        "user_id": run.user_id,
        "mode": run.mode,
        "status": run.status,
        "input_text": run.input_text,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    user_id: str = Depends(get_user_id),
    format: str = Query(default="json"),
) -> dict[str, object]:
    try:
        run = session.get(Run, run_id)
        if run is None or run.user_id != user_id:
            raise http_error("not_found", "Run not found", status_code=404)

        sentences = session.query(SentenceRecord).filter_by(run_id=run_id).all()
        verdicts = {
            verdict.sentence_id: verdict
            for verdict in session.query(VerdictRecord).filter(
                VerdictRecord.sentence_id.in_([s.id for s in sentences])
            )
        }
        evaluations = (
            session.query(EvaluationRecord)
            .filter(EvaluationRecord.sentence_id.in_([s.id for s in sentences]))
            .all()
        )
        article_ids = {evaluation.article_id for evaluation in evaluations}
        articles = {
            article.id: article
            for article in session.query(ArticleRecord).filter(ArticleRecord.id.in_(article_ids))
        }

        payload: dict[str, object] = {
            "run": _serialize_run(run),
            "sentences": [
                {
                    "id": s.id,
                    "text": s.text,
                    "sentence_with_context": s.sentence_with_context,
                    "rewrite_applied": s.rewrite_applied,
                    "needs_reference": s.needs_reference,
                    "reason": s.reason,
                }
                for s in sentences
            ],
            "verdicts": {
                sid: {
                    "overall_assessment": v.overall_assessment,
                    "confidence": v.confidence,
                    "primary_sources": v.primary_sources,
                    "primary_source_identifiers": v.primary_source_identifiers,
                    "synthesis": v.synthesis,
                    "suggested_citation": v.suggested_citation,
                    "suggested_rewording": v.suggested_rewording,
                }
                for sid, v in verdicts.items()
            },
            "evaluations": [
                {
                    "sentence_id": ev.sentence_id,
                    "article_id": ev.article_id,
                    "relevance_score": ev.relevance_score,
                    "relevance_reasoning": ev.relevance_reasoning,
                    "is_relevant": ev.is_relevant,
                    "stance": ev.stance,
                    "stance_confidence": ev.stance_confidence,
                    "stance_reasoning": ev.stance_reasoning,
                    "supporting_evidence": ev.supporting_evidence,
                    "suggested_modification": ev.suggested_modification,
                }
                for ev in evaluations
            ],
        }
        if format == "markdown":
            payload["report"] = build_run_report(
                run.id,
                sentences,
                verdicts,
                evaluations,
                articles,
            )
        return payload
    finally:
        session.close()
