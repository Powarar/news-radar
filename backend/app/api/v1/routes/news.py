from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import UserTopicPreference
from app.repositories.news import NewsRepository
from app.schemas.news import NewsReactionRequest
from app.api.v1.deps import CurrentUser, OptionalUser
from app.services.news import NewsService

router = APIRouter()


def get_news_repo(db: Annotated[AsyncSession, Depends(get_db)]) -> NewsRepository:
    return NewsRepository(db)

def get_news_service(db: Annotated[AsyncSession, Depends(get_db)]) -> NewsService:
    return NewsService(db)

@router.get("/")
async def get_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: OptionalUser = None,
    repo: NewsRepository = Depends(get_news_repo),
    db: AsyncSession = Depends(get_db),
):
    language: str | None = None
    preferred_topics: list[str] | None = None

    if user:
        language = user.language
        result = await db.execute(
            select(UserTopicPreference.topic)
            .where(UserTopicPreference.user_id == user.id, UserTopicPreference.weight > 0)
        )
        topics = result.scalars().all()
        if topics:
            preferred_topics = list(topics)

    items, total = await repo.get_feed(
        limit, offset,
        user_id=user.id if user else None,
        language=language,
        preferred_topics=preferred_topics,
    )
    return {"items": items, "offset": offset, "limit": limit, "total": total}


@router.get("/{news_id}")
async def get_news(news_id: int, repo: NewsRepository = Depends(get_news_repo)):
    item = await repo.get_by_id(news_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item

@router.post("/{news_id}/react")
async def post_reaction(
    news_id: int,
    body: NewsReactionRequest,
    user: CurrentUser,
    service: NewsService = Depends(get_news_service),
    repo: NewsRepository = Depends(get_news_repo),
):
    exists = await repo.get_by_id(news_id)
    if not exists:
        raise HTTPException(404, "News not found")
    await service.react(user.id, news_id, body.reaction)
    counts = await repo.get_reaction_counts(news_id)
    return counts 
