"""Enrichment endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from refweaver.api.dependencies import (
    enforce_request_size,
    get_user_id,
    rate_limit_user,
    verify_api_key,
)
from refweaver.api.settings import SETTINGS
from refweaver.enrich import ArticleEnricher
from refweaver.models import Article

router = APIRouter(
    tags=["enrich"],
    dependencies=[Depends(verify_api_key), Depends(rate_limit_user), Depends(enforce_request_size)],
)


class EnrichRequest(BaseModel):
    articles: list[Article] = Field(..., description="Articles to enrich")
    try_llm: bool = Field(default=False)

    @field_validator("articles")
    @classmethod
    def validate_articles(cls, value: list[Article]) -> list[Article]:
        if not value:
            raise ValueError("articles must be non-empty")
        return value


@router.post("/enrich")
def enrich_articles(
    payload: EnrichRequest,
    user_id: str = Depends(get_user_id),
) -> dict[str, object]:
    enricher = ArticleEnricher(
        semantic_scholar_api_key=SETTINGS.semantic_scholar_api_key,
        openalex_email=SETTINGS.openalex_email,
        use_llm_extractor=payload.try_llm,
    )
    enriched = [
        enricher.fill_abstract(article=a, try_llm=payload.try_llm) for a in payload.articles
    ]
    return {"results": [article.model_dump(mode="json") for article in enriched]}
