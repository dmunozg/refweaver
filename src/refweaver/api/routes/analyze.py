"""Analysis endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from refweaver.api.dependencies import get_db_session, get_user_id, rate_limit_user, verify_api_key
from refweaver.api.schemas import AnalyzeRequest, AnalyzeResponse
from refweaver.api.settings import SETTINGS
from refweaver.db.persist import create_queued_run
from refweaver.jobs import analyze_paragraph_job
from refweaver.queue import enqueue_job
from refweaver.text_utils import validate_text_length

router = APIRouter(
    tags=["analysis"],
    dependencies=[Depends(verify_api_key), Depends(rate_limit_user)],
)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_text(
    payload: AnalyzeRequest,
    session: Annotated[Session, Depends(get_db_session)],
    user_id: str = Depends(get_user_id),
) -> AnalyzeResponse:
    validate_text_length(payload.text, max_tokens=SETTINGS.max_input_tokens)

    run_id = uuid4().hex
        try:
            create_queued_run(
                session,
                run_id=run_id,
                user_id=user_id,
                mode=payload.mode,
                input_text=payload.text,
            )
            job_id = enqueue_job(
                "refweaver.jobs.analyze_paragraph_job",
                payload.text,
                run_id=run_id,
                user_id=user_id,
                include_markdown=payload.include_markdown,
            )
        finally:
            session.close()
        return AnalyzeResponse(
            run_id=run_id,
            status="queued",
            job_id=job_id,
            job_url=f"/jobs/{job_id}",
        )

    result = analyze_paragraph_job(
        payload.text,
        run_id=run_id,
        user_id=user_id,
        include_markdown=payload.include_markdown,
    )
    return AnalyzeResponse(
        run_id=run_id,
        status="completed",
        results=result.get("results"),
        markdown_report=result.get("markdown_report"),
    )
