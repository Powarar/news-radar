import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.main import app  # noqa: F401 — импорт регистрирует все модели

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/newsradar_test",
)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with factory() as cleanup:
        for table in reversed(Base.metadata.sorted_tables):
            await cleanup.execute(table.delete())
        await cleanup.commit()


@pytest.fixture
def mock_redis():
    m = AsyncMock()
    m.exists.return_value = 0
    m.get.return_value = None
    m.set.return_value = True
    m.setex.return_value = True
    m.delete.return_value = True
    # Rate limiter uses pipe = await redis.pipeline()
    pipe = AsyncMock()
    pipe.execute.return_value = (0, 0, 0, 0)  # unpacked as (_, count, _, _)
    # Pipeline methods return coroutines in redis-py but are never awaited
    # individually — only execute() is awaited.  return_value=None stops
    # AsyncMock from auto-generating CoroutineMock objects that trigger
    # "coroutine was never awaited" warnings.
    pipe.zremrangebyscore.return_value = None
    pipe.zcard.return_value = None
    pipe.zadd.return_value = None
    pipe.expire.return_value = None
    m.pipeline.return_value = pipe
    return m


@pytest_asyncio.fixture
async def client(db_session, mock_redis, monkeypatch):
    async def override_get_db():
        yield db_session

    monkeypatch.setattr("app.core.redis.redis", mock_redis)
    monkeypatch.setattr("app.core.rate_limit.redis", mock_redis)
    monkeypatch.setattr("app.services.auth.redis", mock_redis)
    monkeypatch.setattr("app.api.v1.deps.redis", mock_redis)

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
