import time

from fastapi import HTTPException, Request, status

from app.core.redis import redis


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

        async with redis.pipeline() as pipe:
            pipe.zremrangebyscore(key, 0, window_start)  # remove old entries
            pipe.zcard(key)                                # count current
            pipe.zadd(key, {str(now): now})                # add current
            pipe.expire(key, self.window_seconds + 1)      # set TTL
            _, count, _, _ = await pipe.execute()

        if count > self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
            )
