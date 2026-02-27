"""Search endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from refweaver.api.dependencies import get_user_id, verify_api_key
from refweaver.api.settings import SETTINGS
from refweaver.enrich import ArticleEnricher
from refweaver.models import Article
from refweaver.search import UnifiedSearch

router = APIRouter(tags=["search"], dependencies=[Depends(verify_api_key)])


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit_per_source: int = Field(default=5, ge=1, le=50)
    enrich: bool = Field(default=False)


@router.post("/search")
def search_articles(
    payload: SearchRequest,
    user_id: str = Depends(get_user_id),
) -> dict[str, object]:
    searcher = UnifiedSearch()
    articles = searcher.search(payload.query, limit_per_source=payload.limit_per_source)
    if payload.enrich:
        enricher = ArticleEnricher(
            semantic_scholar_api_key=SETTINGS.semantic_scholar_api_key,
            openalex_email=SETTINGS.openalex_email,
            use_llm_extractor=False,
        )
        enriched: list[Article] = []
        for article in articles:
            enriched.append(enricher.fill_abstract(article=article, try_llm=False))
        articles = enriched
    return {"results": [article.model_dump(mode="json") for article in articles]}
