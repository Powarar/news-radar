import json

from sqlalchemy import Float, cast, desc, func, literal, or_, select, case
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem, NewsReaction, ReactionType
from app.models.source import Source
from app.models.user import UserSourceSetting, UserTopicPreference


class NewsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_preferences(self, user_id: int) -> dict[str, float]:
        result = await self.db.execute(
            select(UserTopicPreference.topic, UserTopicPreference.weight).where(
                UserTopicPreference.user_id == user_id,
                UserTopicPreference.weight > 0,
            )
        )
        return {row.topic: float(row.weight) for row in result}

    async def get_feed(
        self,
        limit: int,
        offset: int,
        user_id: int | None = None,
        language: str | None = None,
    ) -> tuple[list[dict], int]:
        date_sort = func.coalesce(NewsItem.published_at, NewsItem.created_at)

        stmt = select(NewsItem, Source).join(Source, NewsItem.source_id == Source.id)

        order_by = [desc(date_sort)]

        if user_id:
            blacklisted_sq = (
                select(UserSourceSetting.source_id)
                .where(UserSourceSetting.user_id == user_id, UserSourceSetting.blacklisted)
                .scalar_subquery()
            )
            stmt = stmt.where(NewsItem.source_id.not_in(blacklisted_sq))

            prefs = await self.get_user_preferences(user_id)
            if prefs:
                topics_jsonb = cast(NewsItem.topics, JSONB)
                stmt = stmt.where(
                    or_(
                        NewsItem.topics.is_(None),
                        *[topics_jsonb.has_key(t) for t in prefs],
                    )
                )

                # relevance = Σ(user_weight × news_topic_score)
                score_parts = [
                    case(
                        (topics_jsonb.has_key(topic), weight * cast(topics_jsonb[topic].as_string(), Float)),
                        else_=literal(0.0),
                    )
                    for topic, weight in prefs.items()
                ]
                relevance = score_parts[0]
                for part in score_parts[1:]:
                    relevance = relevance + part

                order_by = [desc(relevance), desc(date_sort)]

        if language:
            stmt = stmt.where(NewsItem.language == language)

        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))

        result = await self.db.execute(stmt.order_by(*order_by).limit(limit).offset(offset))
        rows = result.all()

        user_reactions: dict[int, str] = {}
        counts_map: dict[int, tuple[int, int]] = {}

        if rows:
            news_ids = [row[0].id for row in rows]

            if user_id:
                r = await self.db.execute(
                    select(NewsReaction.news_item_id, NewsReaction.reaction)
                    .where(NewsReaction.user_id == user_id, NewsReaction.news_item_id.in_(news_ids))
                )
                user_reactions = {row.news_item_id: row.reaction for row in r}

            counts_result = await self.db.execute(
                select(
                    NewsReaction.news_item_id,
                    func.sum(case((NewsReaction.reaction == ReactionType.like, 1), else_=0)).label("likes"),
                    func.sum(case((NewsReaction.reaction == ReactionType.dislike, 1), else_=0)).label("dislikes"),
                )
                .where(NewsReaction.news_item_id.in_(news_ids))
                .group_by(NewsReaction.news_item_id)
            )
            counts_map = {row.news_item_id: (row.likes or 0, row.dislikes or 0) for row in counts_result}

        items = [
            self._serialize(news, source, user_reactions.get(news.id), *counts_map.get(news.id, (0, 0)))
            for news, source in rows
        ]
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

    async def get_reaction_counts(self, news_id: int) -> dict:
        result = await self.db.execute(
            select(
                func.sum(case((NewsReaction.reaction == ReactionType.like, 1), else_=0)).label("likes"),
                func.sum(case((NewsReaction.reaction == ReactionType.dislike, 1), else_=0)).label("dislikes"),
            ).where(NewsReaction.news_item_id == news_id)
        )
        row = result.one()
        return {"likes": row.likes or 0, "dislikes": row.dislikes or 0}

    async def add_reaction(self, user_id: int, news_id: int, reaction: ReactionType) -> NewsReaction | None:
        news = await self.db.scalar(select(NewsItem).where(NewsItem.id == news_id))
        if not news:
            raise LookupError(f"NewsItem {news_id} not found")

        if reaction == ReactionType.blacklist:
            await self.set_source_blacklisted(user_id, news.source_id)

        existing = await self.db.scalar(
            select(NewsReaction).where(
                NewsReaction.user_id == user_id,
                NewsReaction.news_item_id == news_id,
            )
        )

        if existing:
            if existing.reaction == reaction:
                await self.db.delete(existing)
                await self.db.commit()
                return None
            existing.reaction = reaction
        else:
            existing = NewsReaction(user_id=user_id, news_item_id=news_id, reaction=reaction)
            self.db.add(existing)

        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    def _serialize(self, news: NewsItem, source: Source, reaction: str | None = None, likes_count: int = 0, dislikes_count: int = 0) -> dict:
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
            "likes_count": likes_count,
            "dislikes_count": dislikes_count,
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
    
