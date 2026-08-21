from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser, OptionalUser
from app.core.database import get_db
from app.core.rate_limit import UserDailyQuota
from app.repositories.news import NewsRepository
from app.schemas.news import NewsReactionRequest
from app.services.ai.news_chat import ChatResponse, answer_news_query
from app.services.news import NewsService

router = APIRouter()


def get_news_repo(db: Annotated[AsyncSession, Depends(get_db)]) -> NewsRepository:
    return NewsRepository(db)

def get_news_service(db: Annotated[AsyncSession, Depends(get_db)]) -> NewsService:
    return NewsService(db)


NewsRepoDep = Annotated[NewsRepository, Depends(get_news_repo)]
NewsServiceDep = Annotated[NewsService, Depends(get_news_service)]


@router.get("/")
async def get_feed(
    user: OptionalUser,
    repo: NewsRepoDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("relevance", pattern="^(relevance|date|importance)$"),
):
    items, total = await repo.get_feed(
        limit, offset,
        user_id=user.id if user else None,
        sort_by=sort,
    )
    return {"items": items, "offset": offset, "limit": limit, "total": total}


@router.get("/{news_id}")
async def get_news(news_id: int, repo: NewsRepoDep):
    item = await repo.get_by_id(news_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item

@router.post("/{news_id}/react")
async def post_reaction(
    news_id: int,
    body: NewsReactionRequest,
    user: CurrentUser,
    service: NewsServiceDep,
    repo: NewsRepoDep,
):
    await service.react(user.id, news_id, body.reaction)
    counts = await repo.get_reaction_counts(news_id)
    return counts



class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1_000)
    days: int = Field(default=3, ge=1, le=7)


chat_daily_quota = UserDailyQuota(resource="news-chat", max_requests=3)


async def enforce_chat_daily_quota(user: CurrentUser) -> None:
    await chat_daily_quota.consume(user.id)


ChatQuotaDep = Annotated[None, Depends(enforce_chat_daily_quota)]

@router.post("/chat", response_model=ChatResponse)
def chat_with_news(
    body: ChatRequest,
    user: CurrentUser,
    _quota: ChatQuotaDep,
):
    return answer_news_query(body.query, days=body.days)
