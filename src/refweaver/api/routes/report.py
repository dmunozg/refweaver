"""Report endpoint."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from refweaver.api.dependencies import get_user_id, rate_limit_user, verify_api_key
from refweaver.api.errors import http_error
from refweaver.api.reporting import build_run_report
from refweaver.api.settings import SETTINGS
from refweaver.db.models import Run, SentenceRecord, VerdictRecord
from refweaver.db.session import get_session

router = APIRouter(
    tags=["report"],
    dependencies=[Depends(verify_api_key), Depends(rate_limit_user)],
)


class ReportRequest(BaseModel):
    run_id: str = Field(..., description="Run identifier")
    format: str = Field(default="markdown", description="markdown|json")

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        allowed = {"markdown", "json"}
        if value not in allowed:
            msg = f"format must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return value


@router.post("/report")
def generate_report(
    payload: ReportRequest,
    user_id: str = Depends(get_user_id),
) -> dict[str, object]:
    session = get_session(SETTINGS.database_url)
    run = session.get(Run, payload.run_id)
    if run is None or run.user_id != user_id:
        raise http_error("not_found", "Run not found", status_code=404)

    sentences = session.query(SentenceRecord).filter_by(run_id=payload.run_id).all()
    verdicts = {
        verdict.sentence_id: verdict
        for verdict in session.query(VerdictRecord).filter(
            VerdictRecord.sentence_id.in_([s.id for s in sentences])
        )
    }
    if payload.format == "json":
        sentence_payloads = []
        for sentence in sentences:
            verdict = verdicts.get(sentence.id)
            sentence_payloads.append(
                {
                    "id": sentence.id,
                    "text": sentence.text,
                    "verdict": verdict.overall_assessment if verdict else None,
                }
            )
        return {"run_id": payload.run_id, "sentences": sentence_payloads}

    report = build_run_report(payload.run_id, sentences, verdicts)
    return {"run_id": payload.run_id, "report": report}
