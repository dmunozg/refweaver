"""Enrichment endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, HttpUrl, field_validator

from refweaver.api.dependencies import get_user_id, rate_limit_user, verify_api_key
from refweaver.api.settings import SETTINGS
from refweaver.enrich import ArticleEnricher
from refweaver.models import Article

router = APIRouter(
    tags=["enrich"],
    dependencies=[Depends(verify_api_key), Depends(rate_limit_user)],
)


class EnrichArticle(BaseModel):
    source: str = Field(..., description="Source API")
    external_id: str = Field(..., description="Source-specific identifier")
    title: str = Field(..., description="Article title")
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None)
    doi: str | None = Field(default=None)
    url: HttpUrl | None = Field(default=None)


class EnrichRequest(BaseModel):
    articles: list[EnrichArticle] = Field(..., description="Articles to enrich")
    try_llm: bool = Field(default=False)

    @field_validator("articles")
    @classmethod
    def validate_articles(cls, value: list[EnrichArticle]) -> list[EnrichArticle]:
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
    enriched = []
    for article in payload.articles:
        model = Article(
            source=article.source,
            external_id=article.external_id,
            title=article.title,
            authors=article.authors,
            year=article.year,
            doi=article.doi,
            url=article.url,
        )
        enriched.append(enricher.fill_abstract(article=model, try_llm=payload.try_llm))
    return {"results": [article.model_dump(mode="json") for article in enriched]}
