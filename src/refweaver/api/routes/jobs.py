"""Job status endpoints."""

from fastapi import APIRouter, Depends

from refweaver.api.dependencies import get_user_id, rate_limit_user, verify_api_key
from refweaver.api.errors import http_error
from refweaver.queue import fetch_job

router = APIRouter(
    tags=["jobs"],
    dependencies=[Depends(verify_api_key), Depends(rate_limit_user)],
)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user_id: str = Depends(get_user_id)) -> dict[str, object]:
    payload = fetch_job(job_id)
    if payload.get("user_id") != user_id:
        raise http_error("not_found", "Job not found", status_code=404)
    return payload
