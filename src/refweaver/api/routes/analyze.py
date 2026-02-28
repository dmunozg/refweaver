"""Analysis endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends

from refweaver.api.dependencies import get_user_id, rate_limit_user, verify_api_key
from refweaver.api.errors import http_error
from refweaver.api.schemas import AnalyzeRequest, AnalyzeResponse
from refweaver.api.settings import SETTINGS
from refweaver.db.persist import create_queued_run
from refweaver.db.session import get_session
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
    user_id: str = Depends(get_user_id),
) -> AnalyzeResponse:
    if payload.mode not in {"sentence", "paragraph", "document"}:
        raise http_error("invalid_mode", "mode must be sentence|paragraph|document")

    validate_text_length(payload.text, max_tokens=SETTINGS.max_input_tokens)

    run_id = uuid4().hex
    if payload.async_mode or len(payload.text) > SETTINGS.run_async_threshold:
        session = get_session(SETTINGS.database_url)
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
