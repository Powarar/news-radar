import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.redis import redis

# Lua script: atomically clean old entries, count remaining, add new entry, refresh TTL.
# KEYS[1] — sorted set key
# ARGV[1] — window start (cutoff timestamp)
# ARGV[2] — new entry score (now)
# ARGV[3] — unique member
# ARGV[4] — TTL seconds
_SLIDING_WINDOW_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
local count = redis.call('ZCARD', KEYS[1])
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[3])
redis.call('EXPIRE', KEYS[1], ARGV[4])
return count
"""

# Fixed daily window is deliberate here: product requirement is a small,
# understandable allowance (three chat requests per UTC day), not a generic
# anti-abuse sliding window. INCR and EXPIRE run in one Redis script, so two
# concurrent requests cannot both consume the same remaining slot.
_DAILY_QUOTA_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


def _client_ip(request: Request) -> str:
    """Resolve the visitor address only when trusted proxy handling is enabled."""
    if settings.trust_proxy_headers:
        cloudflare_ip = request.headers.get("CF-Connecting-IP")
        if cloudflare_ip:
            return cloudflare_ip.strip()

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",", maxsplit=1)[0].strip()

    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Simple sliding-window rate limiter backed by Redis."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, request: Request):
        client_ip = _client_ip(request)
        key = f"ratelimit:{client_ip}:{request.url.path}"

        now = time.time()
        window_start = now - self.window_seconds

        count = await redis.eval(
            _SLIDING_WINDOW_SCRIPT,
            1,
            key,
            window_start,
            now,
            f"{now}:{uuid.uuid4().hex}",
            self.window_seconds + 1,
        )

        if count >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
                headers={"Retry-After": str(self.window_seconds)},
            )


class UserDailyQuota:
    """Fixed daily request quota for an authenticated user, backed by Redis."""

    def __init__(self, resource: str, max_requests: int):
        self.resource = resource
        self.max_requests = max_requests

    async def consume(self, user_id: int) -> None:
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        ttl_seconds = max(1, int((tomorrow - now).total_seconds()))
        key = f"quota:{self.resource}:{user_id}:{now.date().isoformat()}"
        count = await redis.eval(_DAILY_QUOTA_SCRIPT, 1, key, ttl_seconds)

        if count > self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Daily limit reached: {self.max_requests} requests. "
                    "Try again tomorrow."
                ),
                headers={"Retry-After": str(ttl_seconds)},
            )
