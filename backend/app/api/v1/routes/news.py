from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.news import NewsRepository

router = APIRouter()


def get_repo(db: Annotated[AsyncSession, Depends(get_db)]) -> NewsRepository:
    return NewsRepository(db)


@router.get("/")
async def get_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: NewsRepository = Depends(get_repo),
):
    items, total = await repo.get_feed(limit, offset)
    return {"items": items, "offset": offset, "limit": limit, "total": total}


@router.get("/{news_id}")
async def get_news(news_id: int, repo: NewsRepository = Depends(get_repo)):
    item = await repo.get_by_id(news_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item
