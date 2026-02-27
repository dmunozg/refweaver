"""Job status endpoints."""

from fastapi import APIRouter, Depends

from refweaver.api.dependencies import verify_api_key
from refweaver.queue import fetch_job

router = APIRouter(tags=["jobs"], dependencies=[Depends(verify_api_key)])


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    return fetch_job(job_id)
