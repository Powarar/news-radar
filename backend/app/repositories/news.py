import json

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem
from app.models.source import Source


class NewsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_feed(self, limit: int, offset: int) -> tuple[list[dict], int]:
        sort_by = func.coalesce(NewsItem.published_at, NewsItem.created_at)

        result = await self.db.execute(
            select(NewsItem, Source)
            .join(Source, NewsItem.source_id == Source.id)
            .order_by(desc(sort_by))
            .limit(limit)
            .offset(offset)
        )
        total = await self.db.scalar(select(func.count()).select_from(NewsItem))

        items = [self._serialize(news, source) for news, source in result.all()]
        return items, total or 0

    async def get_by_id(self, news_id: int) -> dict | None:
        result = await self.db.execute(
            select(NewsItem, Source)
            .join(Source, NewsItem.source_id == Source.id)
            .where(NewsItem.id == news_id)
        )
        row = result.first()
        if not row:
            return None
        return self._serialize(*row)

    def _serialize(self, news: NewsItem, source: Source) -> dict:
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
