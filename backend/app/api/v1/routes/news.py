import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.news import NewsItem
from app.models.source import Source

router = APIRouter()


@router.get("/")
async def get_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает список новостей, отсортированных по дате (новые первые).
    limit  — сколько взять (макс 100)
    offset — сколько пропустить (для пагинации)
    """
    result = await db.execute(
        select(NewsItem, Source)
        .join(Source, NewsItem.source_id == Source.id)
        .order_by(desc(NewsItem.created_at))
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    items = []
    for news, source in rows:
        items.append({
            "id": news.id,
            "title": news.title,
            "body": news.body,
            "summary": news.summary,
            "url": news.url,
            "image_url": news.image_url,
            "language": news.language,
            "topics": json.loads(news.topics) if news.topics else {},
            "importance_score": news.importance_score,
            "published_at": news.published_at.isoformat() if news.published_at else None,
            "created_at": news.created_at.isoformat(),
            "source": {
                "id": source.id,
                "name": source.name,
                "url": source.url,
                "type": source.type,
                "language": source.language,
                "country": source.country,
                "topics": json.loads(source.topics) if source.topics else [],
                "enabled": True,
                "blacklisted": False,
            },
        })

    return {"items": items, "offset": offset, "limit": limit}


@router.get("/{news_id}")
async def get_news(news_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NewsItem, Source.name.label("source_name"))
        .join(Source, NewsItem.source_id == Source.id)
        .where(NewsItem.id == news_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    news, source = row
    return {
        "id": news.id,
        "title": news.title,
        "body": news.body,
        "summary": news.summary,
        "url": news.url,
        "image_url": news.image_url,
        "language": news.language,
        "topics": json.loads(news.topics) if news.topics else {},
        "importance_score": news.importance_score,
        "published_at": news.published_at.isoformat() if news.published_at else None,
        "created_at": news.created_at.isoformat(),
        "source": {
            "id": source.id,
            "name": source.name,
            "url": source.url,
            "type": source.type,
            "language": source.language,
            "country": source.country,
            "topics": json.loads(source.topics) if source.topics else [],
            "enabled": True,
            "blacklisted": False,
        },
    }
