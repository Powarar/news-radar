import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.rate_limit import RateLimiter, UserDailyQuota, _client_ip


def make_request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": headers or [],
        "client": ("10.0.0.5", 12345),
        "server": ("test", 80),
        "scheme": "http",
        "query_string": b"",
    })


@pytest.mark.asyncio
async def test_rate_limiter_rejects_request_at_limit(mock_redis, monkeypatch):
    mock_redis.eval.return_value = 5
    monkeypatch.setattr("app.core.rate_limit.redis", mock_redis)
    limiter = RateLimiter(max_requests=5, window_seconds=60)

    with pytest.raises(HTTPException) as exc:
        await limiter(make_request())

    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": "60"}


@pytest.mark.asyncio
async def test_user_daily_quota_rejects_fourth_chat_request(mock_redis, monkeypatch):
    mock_redis.eval.return_value = 4
    monkeypatch.setattr("app.core.rate_limit.redis", mock_redis)
    quota = UserDailyQuota(resource="news-chat", max_requests=3)

    with pytest.raises(HTTPException) as exc:
        await quota.consume(user_id=42)

    assert exc.value.status_code == 429
    assert "Daily limit reached: 3" in exc.value.detail
    assert mock_redis.eval.await_count == 1


def test_proxy_header_used_only_when_trusted(monkeypatch):
    request = make_request([(b"cf-connecting-ip", b"203.0.113.10")])

    monkeypatch.setattr("app.core.rate_limit.settings.trust_proxy_headers", False)
    assert _client_ip(request) == "10.0.0.5"

    monkeypatch.setattr("app.core.rate_limit.settings.trust_proxy_headers", True)
    assert _client_ip(request) == "203.0.113.10"
