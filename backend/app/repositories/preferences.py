from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, UserTopicPreference


class PreferencesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_with_preferences(self, user_id: int) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.preferences))
        )
        return result.scalar_one_or_none()

    async def set_preferences(self, user_id: int, topics: dict[str, float]) -> list[UserTopicPreference]:
        await self.db.execute(
            delete(UserTopicPreference).where(UserTopicPreference.user_id == user_id)
        )
        prefs = [
            UserTopicPreference(user_id=user_id, topic=topic, weight=weight)
            for topic, weight in topics.items()
        ]
        self.db.add_all(prefs)
        await self.db.commit()
        return prefs
