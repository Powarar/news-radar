from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
):
    items, total = await repo.get_feed(limit, offset, user_id=user.id if user else None)
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
    service: NewsService = Depends(get_news_service)
    ):
    result = await service.react(user.id, news_id, body.reaction)                                                                                                   
    if not result:                                                                                                                                                  
        raise HTTPException(404, "News not found")
    return result 
