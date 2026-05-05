import json

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem, NewsReaction, ReactionType
from app.models.source import Source
from app.models.user import UserSourceSetting


class NewsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_feed(self, limit: int, offset: int, user_id: int | None = None) -> tuple[list[dict], int]:
        sort_by = func.coalesce(NewsItem.published_at, NewsItem.created_at)

        stmt = select(NewsItem, Source).join(Source, NewsItem.source_id == Source.id)

        if user_id:
            blacklisted_sq = (
                select(UserSourceSetting.source_id)
                .where(UserSourceSetting.user_id == user_id, UserSourceSetting.blacklisted)
                .scalar_subquery()
            )
            stmt = stmt.where(NewsItem.source_id.not_in(blacklisted_sq))

        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))

        result = await self.db.execute(stmt.order_by(desc(sort_by)).limit(limit).offset(offset))
        rows = result.all()

        user_reactions: dict[int, str] = {}
        if user_id and rows:
            news_ids = [row[0].id for row in rows]
            r = await self.db.execute(
                select(NewsReaction.news_item_id, NewsReaction.reaction)
                .where(NewsReaction.user_id == user_id, NewsReaction.news_item_id.in_(news_ids))
            )
            user_reactions = {row.news_item_id: row.reaction for row in r}

        items = [self._serialize(news, source, user_reactions.get(news.id)) for news, source in rows]
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
    
    async def set_source_blacklisted(self, user_id: int, source_id: int) -> None:
        setting = await self.db.scalar(
            select(UserSourceSetting).where(
                UserSourceSetting.user_id == user_id,
                UserSourceSetting.source_id == source_id,
            )
        )
        if setting:
            setting.blacklisted = True
        else:
            self.db.add(UserSourceSetting(user_id=user_id, source_id=source_id, blacklisted=True))

    async def add_reaction(self, user_id: int, news_id: int, reaction: ReactionType) -> NewsReaction | None:
        news = await self.db.scalar(select(NewsItem).where(NewsItem.id == news_id))
        if not news:
            return None

        if reaction == ReactionType.blacklist:
            await self.set_source_blacklisted(user_id, news.source_id)                                                                                                                                                 
                                                                                                                                                                        
        existing = await self.db.scalar(
            select(NewsReaction).where(
                NewsReaction.user_id == user_id,                                                                                                                        
                NewsReaction.news_item_id == news_id,
            )                                                                                                                                                           
        )           

        if existing:
            existing.reaction = reaction
        else:
            existing = NewsReaction(user_id=user_id, news_item_id=news_id, reaction=reaction)                                                                           
            self.db.add(existing)
                                                                                                                                                                        
        await self.db.commit()
        await self.db.refresh(existing)
        return existing    

    def _serialize(self, news: NewsItem, source: Source, reaction: str | None = None) -> dict:
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
            "reaction": reaction,
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
    
