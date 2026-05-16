import time

from fastapi import HTTPException, Request, status

from app.core.redis import redis

# Lua script: atomically clean old entries, count remaining, add new entry, refresh TTL.
# KEYS[1] — sorted set key
# ARGV[1] — window start (cutoff timestamp)
# ARGV[2] — new entry score & member (now)
# ARGV[3] — TTL seconds
_SLIDING_WINDOW_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
local count = redis.call('ZCARD', KEYS[1])
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return count
"""


class RateLimiter:
    """Simple sliding-window rate limiter backed by Redis."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, request: Request):
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}:{request.url.path}"

        now = time.time()
        window_start = now - self.window_seconds

        count = await redis.eval(
            _SLIDING_WINDOW_SCRIPT,
            1,
            key,
            window_start,
            now,
            self.window_seconds + 1,
        )

        if count > self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
            )
