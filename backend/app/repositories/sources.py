import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source, SourceType
from app.models.user import UserSourceSetting


class SourcesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[dict]:
        result = await self.db.execute(select(Source).order_by(Source.name))
        sources = result.scalars().all()
        return [self._serialize(s, None) for s in sources]

    async def list_for_user(self, user_id: int) -> list[dict]:
        result = await self.db.execute(select(Source).order_by(Source.name))
        sources = result.scalars().all()

        settings_result = await self.db.execute(
            select(UserSourceSetting).where(UserSourceSetting.user_id == user_id)
        )
        settings_map = {s.source_id: s for s in settings_result.scalars().all()}

        return [
            self._serialize(s, settings_map.get(s.id))
            for s in sources
        ]

    async def create(self, data: dict) -> Source:
        source = Source(
            name=data["name"],
            url=data["url"],
            type=SourceType(data["type"]),
            language=data.get("language", "en"),
            country=data.get("country"),
            topics=json.dumps(data["topics"]) if data.get("topics") else None,
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        return source

    async def get_by_id(self, source_id: int) -> Source | None:
        return await self.db.scalar(select(Source).where(Source.id == source_id))

    async def _get_or_create_setting(self, user_id: int, source_id: int) -> UserSourceSetting:
        setting = await self.db.scalar(
            select(UserSourceSetting).where(
                UserSourceSetting.user_id == user_id,
                UserSourceSetting.source_id == source_id,
            )
        )
        if setting is None:
            setting = UserSourceSetting(user_id=user_id, source_id=source_id)
            self.db.add(setting)
            await self.db.flush()
        return setting

    async def toggle(self, user_id: int, source_id: int) -> dict | None:
        source = await self.get_by_id(source_id)
        if not source:
            return None
        setting = await self._get_or_create_setting(user_id, source_id)
        setting.enabled = not setting.enabled
        await self.db.commit()
        return self._serialize(source, setting)

    async def set_blacklist(self, user_id: int, source_id: int, blacklisted: bool) -> dict | None:
        source = await self.get_by_id(source_id)
        if not source:
            return None
        setting = await self._get_or_create_setting(user_id, source_id)
        setting.blacklisted = blacklisted
        await self.db.commit()
        return self._serialize(source, setting)

    def _serialize(self, source: Source, setting: UserSourceSetting | None) -> dict:
        return {
            "id": source.id,
            "name": source.name,
            "url": source.url,
            "type": source.type.value if hasattr(source.type, "value") else source.type,
            "language": source.language,
            "country": source.country,
            "topics": json.loads(source.topics) if source.topics else None,
            "enabled": setting.enabled if setting else True,
            "blacklisted": setting.blacklisted if setting else False,
        }
