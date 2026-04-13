import redis.asyncio as aioredis

from app.core.config import settings

# создаём пул соединений к Redis — переиспользуется между запросами
redis = aioredis.from_url(settings.redis_url, decode_responses=True)
