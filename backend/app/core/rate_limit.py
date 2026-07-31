import time
import uuid

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
