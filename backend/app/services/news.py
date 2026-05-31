from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsReaction, ReactionType
from app.repositories.news import NewsRepository


class NewsService:
    def __init__(self, db: AsyncSession):
        self.repo = NewsRepository(db)

    async def react(self, user_id: int, news_id: int, reaction: ReactionType) -> NewsReaction | None:
        # LookupError от репозитория не ловим — пусть всплывает в route
        result = await self.repo.add_reaction(user_id, news_id, reaction)

        if result is not None:
            from app.workers.tasks import update_topic_preferences
            update_topic_preferences.delay(user_id, news_id, reaction.value)

        return result
