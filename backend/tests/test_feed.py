"""Tests for the feed endpoint — sorting, ranking, filtering."""

import json
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.news import NewsItem, ReactionType
from app.models.source import Source
from app.models.user import User, UserSourceSetting, UserTopicPreference
from app.repositories.news import NewsRepository

BASE = "/api/v1/news"

# ─── Helpers ───────────────────────────────────────────────────────────────────


async def make_user(db_session: AsyncSession, **overrides) -> User:
    u = User(
        email=overrides.get("email", "feed@test.com"),
        username=overrides.get("username", "feeduser"),
        hashed_password="$2b$12$dummyhash",  # won't be used in tests
        language=overrides.get("language", "ru"),
    )
    db_session.add(u)
    await db_session.commit()
    return u


async def make_source(db_session: AsyncSession, **overrides) -> Source:
    s = Source(
        name=overrides.get("name", "Test Source"),
        url=overrides.get("url", "https://test.example.com"),
        type=overrides.get("type", "website"),
        language=overrides.get("language", "ru"),
        topics=json.dumps(overrides.get("topics", ["technology"])),
    )
    db_session.add(s)
    await db_session.commit()
    return s


async def make_news(
    db_session: AsyncSession,
    source_id: int,
    **overrides,
) -> NewsItem:
    """Create a news item with sensible defaults. Override any field."""
    n = NewsItem(
        source_id=source_id,
        title=overrides.get("title", "Test News"),
        body=overrides.get("body", "Test body content for the news item."),
        topics=overrides.get("topics", {"technology": 0.9}),
        importance_score=overrides.get("importance_score", 0.5),
        published_at=overrides.get("published_at", datetime.now(timezone.utc)),
        language=overrides.get("language", "ru"),
    )
    db_session.add(n)
    await db_session.commit()
    return n


def auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


# ─── Anonymous ────────────────────────────────────────────────────────────────


class TestAnonymousFeed:
    """Unauthenticated users should get date-sorted feed."""

    async def test_anonymous_gets_date_order(self, client: AsyncClient, db_session: AsyncSession):
        src = await make_source(db_session)
        old = await make_news(db_session, src.id, published_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
        new = await make_news(db_session, src.id, published_at=datetime(2025, 6, 1, tzinfo=timezone.utc))

        r = await client.get(f"{BASE}/")
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["items"]]
        assert ids == [new.id, old.id]

    async def test_anonymous_relevance_falls_back_to_date(self, client: AsyncClient, db_session: AsyncSession):
        """Anonymous user requesting relevance sort gets date order."""
        src = await make_source(db_session)
        await make_news(db_session, src.id)
        r = await client.get(f"{BASE}/?sort=relevance")
        assert r.status_code == 200

    async def test_anonymous_importance_works(self, client: AsyncClient, db_session: AsyncSession):
        """Importance sort works without auth."""
        src = await make_source(db_session)
        n1 = await make_news(db_session, src.id, importance_score=0.9)
        n2 = await make_news(db_session, src.id, importance_score=0.1)
        r = await client.get(f"{BASE}/?sort=importance")
        ids = [i["id"] for i in r.json()["items"]]
        assert ids == [n1.id, n2.id]


# ─── Date sort ─────────────────────────────────────────────────────────────────


class TestDateSort:
    async def test_date_descending(self, client: AsyncClient, db_session: AsyncSession):
        user = await make_user(db_session)
        src = await make_source(db_session)
        old = await make_news(db_session, src.id, published_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
        new = await make_news(db_session, src.id, published_at=datetime(2025, 6, 1, tzinfo=timezone.utc))

        r = await client.get(f"{BASE}/?sort=date", headers=auth_headers(user))
        ids = [i["id"] for i in r.json()["items"]]
        assert ids == [new.id, old.id]


# ─── Importance sort ───────────────────────────────────────────────────────────


class TestImportanceSort:
    async def test_importance_descending(self, client: AsyncClient, db_session: AsyncSession):
        user = await make_user(db_session)
        src = await make_source(db_session)
        n_high = await make_news(db_session, src.id, importance_score=0.9)
        n_low = await make_news(db_session, src.id, importance_score=0.1)

        r = await client.get(f"{BASE}/?sort=importance", headers=auth_headers(user))
        ids = [i["id"] for i in r.json()["items"]]
        assert ids == [n_high.id, n_low.id]


# ─── Relevance sort ────────────────────────────────────────────────────────────


class TestRelevanceSort:
    """Core ranking algorithm tests."""

    async def test_relevance_ranking(self, client: AsyncClient, db_session: AsyncSession):
        """News matching user preferences should rank higher."""
        user = await make_user(db_session)
        db_session.add(UserTopicPreference(user_id=user.id, topic="technology", weight=0.9))
        db_session.add(UserTopicPreference(user_id=user.id, topic="sports", weight=0.1))
        await db_session.commit()

        src = await make_source(db_session)
        tech_news = await make_news(db_session, src.id, topics={"technology": 0.9, "sports": 0.1})
        sports_news = await make_news(db_session, src.id, topics={"technology": 0.1, "sports": 0.9})

        r = await client.get(f"{BASE}/?sort=relevance", headers=auth_headers(user))
        ids = [i["id"] for i in r.json()["items"]]
        # tech_news: 0.9*0.9 + 0.1*0.1 = 0.82
        # sports_news: 0.9*0.1 + 0.1*0.9 = 0.18
        assert ids == [tech_news.id, sports_news.id]

    async def test_topic_exclusion(self, client: AsyncClient, db_session: AsyncSession):
        """News with an excluded topic (weight=0) should be hidden at any score."""
        user = await make_user(db_session)
        db_session.add(UserTopicPreference(user_id=user.id, topic="technology", weight=0.0))
        db_session.add(UserTopicPreference(user_id=user.id, topic="sports", weight=0.8))
        await db_session.commit()

        src = await make_source(db_session)
        high = await make_news(db_session, src.id, topics={"technology": 0.9, "sports": 0.1})
        low = await make_news(db_session, src.id, topics={"technology": 0.3, "sports": 0.9})
        clean = await make_news(db_session, src.id, topics={"sports": 0.9})

        r = await client.get(f"{BASE}/?sort=relevance", headers=auth_headers(user))
        ids = [i["id"] for i in r.json()["items"]]
        assert high.id not in ids   # excluded topic присутствует
        assert low.id not in ids    # excluded topic присутствует даже с низким скором
        assert clean.id in ids      # только любимая тема — показываем

    async def test_source_blacklist(self, client: AsyncClient, db_session: AsyncSession):
        """Blacklisted sources should be excluded from feed."""
        user = await make_user(db_session)
        src = await make_source(db_session)
        db_session.add(UserSourceSetting(user_id=user.id, source_id=src.id, blacklisted=True))
        await db_session.commit()

        await make_news(db_session, src.id)
        r = await client.get(f"{BASE}/", headers=auth_headers(user))
        assert len(r.json()["items"]) == 0

    async def test_disabled_source_is_excluded(self, client: AsyncClient, db_session: AsyncSession):
        user = await make_user(db_session)
        src = await make_source(db_session)
        db_session.add(
            UserSourceSetting(
                user_id=user.id,
                source_id=src.id,
                enabled=False,
            )
        )
        await db_session.commit()

        await make_news(db_session, src.id)
        r = await client.get(f"{BASE}/", headers=auth_headers(user))

        assert r.json()["items"] == []

    async def test_no_preferences_falls_back_to_date(self, client: AsyncClient, db_session: AsyncSession):
        """User with no preferences should get date-sorted feed."""
        now = datetime.now(timezone.utc)
        user = await make_user(db_session)
        src = await make_source(db_session)
        old = await make_news(db_session, src.id, published_at=now - timedelta(days=2))
        new = await make_news(db_session, src.id, published_at=now)

        r = await client.get(f"{BASE}/?sort=relevance", headers=auth_headers(user))
        ids = [i["id"] for i in r.json()["items"]]
        assert ids == [new.id, old.id]

    async def test_no_preferences_still_excludes_stale_news(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        now = datetime.now(timezone.utc)
        user = await make_user(db_session)
        src = await make_source(db_session)
        recent = await make_news(db_session, src.id, published_at=now)
        stale = await make_news(
            db_session,
            src.id,
            published_at=now - timedelta(days=4),
        )

        r = await client.get(f"{BASE}/?sort=relevance", headers=auth_headers(user))
        payload = r.json()
        ids = [i["id"] for i in payload["items"]]
        assert ids == [recent.id]
        assert stale.id not in ids
        assert payload["total"] == 1

    async def test_relevance_threshold(self, client: AsyncClient, db_session: AsyncSession):
        """News with relevance ≤ 0.05 should be filtered out."""
        user = await make_user(db_session)
        db_session.add(UserTopicPreference(user_id=user.id, topic="technology", weight=0.1))
        await db_session.commit()

        src = await make_source(db_session)
        below_threshold = await make_news(db_session, src.id, topics={"technology": 0.4})
        above_threshold = await make_news(db_session, src.id, topics={"technology": 0.9})

        r = await client.get(f"{BASE}/?sort=relevance", headers=auth_headers(user))
        ids = [i["id"] for i in r.json()["items"]]
        # 0.1 * 0.4 = 0.04 → filtered
        # 0.1 * 0.9 = 0.09 → kept
        assert below_threshold.id not in ids
        assert above_threshold.id in ids


# ─── Decay ─────────────────────────────────────────────────────────────────────


class TestPersonalizedFreshness:
    """Personalized feed gives freshness real weight and has a hard age cutoff."""

    async def test_fresh_news_beats_old_news_same_relevance(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        now = datetime.now(timezone.utc)
        user = await make_user(db_session)
        db_session.add(UserTopicPreference(user_id=user.id, topic="technology", weight=0.8))
        await db_session.commit()

        src = await make_source(db_session)
        old = await make_news(db_session, src.id, topics={"technology": 0.9}, published_at=now - timedelta(hours=25))
        fresh = await make_news(db_session, src.id, topics={"technology": 0.9}, published_at=now)

        r = await client.get(f"{BASE}/?sort=relevance", headers=auth_headers(user))
        ids = [i["id"] for i in r.json()["items"]]
        assert ids == [fresh.id, old.id]

    async def test_preferences_outweigh_freshness(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        now = datetime.now(timezone.utc)
        user = await make_user(db_session)
        db_session.add(UserTopicPreference(user_id=user.id, topic="technology", weight=1.0))
        await db_session.commit()

        src = await make_source(db_session)
        preferred = await make_news(
            db_session,
            src.id,
            topics={"technology": 0.9},
            published_at=now - timedelta(days=2),
        )
        merely_fresh = await make_news(
            db_session,
            src.id,
            topics={"technology": 0.2},
            published_at=now,
        )

        r = await client.get(f"{BASE}/?sort=relevance", headers=auth_headers(user))
        ids = [i["id"] for i in r.json()["items"]]
        assert ids == [preferred.id, merely_fresh.id]

    async def test_fresh_relevant_news_can_displace_old_high_relevance_news(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        now = datetime.now(timezone.utc)
        user = await make_user(db_session)
        db_session.add(UserTopicPreference(user_id=user.id, topic="technology", weight=1.0))
        await db_session.commit()

        src = await make_source(db_session)
        old_high_relevance = await make_news(
            db_session,
            src.id,
            topics={"technology": 0.9},
            published_at=now - timedelta(days=2),
        )
        fresh_relevant = await make_news(
            db_session,
            src.id,
            topics={"technology": 0.55},
            published_at=now,
        )

        r = await client.get(f"{BASE}/?sort=relevance", headers=auth_headers(user))
        ids = [i["id"] for i in r.json()["items"]]
        assert ids == [fresh_relevant.id, old_high_relevance.id]

    async def test_news_older_than_three_days_is_excluded(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        now = datetime.now(timezone.utc)
        user = await make_user(db_session)
        db_session.add(UserTopicPreference(user_id=user.id, topic="technology", weight=1.0))
        await db_session.commit()

        src = await make_source(db_session)
        recent = await make_news(
            db_session,
            src.id,
            topics={"technology": 0.8},
            published_at=now - timedelta(days=2, hours=23),
        )
        stale = await make_news(
            db_session,
            src.id,
            topics={"technology": 1.0},
            published_at=now - timedelta(days=3, minutes=1),
        )

        r = await client.get(f"{BASE}/?sort=relevance", headers=auth_headers(user))
        payload = r.json()
        ids = [i["id"] for i in payload["items"]]
        assert recent.id in ids
        assert stale.id not in ids
        assert payload["total"] == 1


# ─── Reaction state transitions ───────────────────────────────────────────────


class TestReactionPreferenceDelta:
    async def test_add_remove_and_replace_return_exact_delta(self, db_session: AsyncSession):
        user = await make_user(db_session)
        source = await make_source(db_session)
        news = await make_news(db_session, source.id)
        repo = NewsRepository(db_session)

        reaction, delta = await repo.add_reaction(user.id, news.id, ReactionType.like)
        assert reaction is not None
        assert delta == 0.2

        reaction, delta = await repo.add_reaction(user.id, news.id, ReactionType.like)
        assert reaction is None
        assert delta == -0.2

        reaction, delta = await repo.add_reaction(user.id, news.id, ReactionType.dislike)
        assert reaction is not None
        assert delta == -0.2

        reaction, delta = await repo.add_reaction(user.id, news.id, ReactionType.like)
        assert reaction is not None
        assert delta == 0.4


# ─── Pagination ────────────────────────────────────────────────────────────────


class TestPagination:
    async def test_limit_offset(self, client: AsyncClient, db_session: AsyncSession):
        src = await make_source(db_session)
        n1 = await make_news(db_session, src.id, published_at=datetime(2025, 6, 3, tzinfo=timezone.utc))
        n2 = await make_news(db_session, src.id, published_at=datetime(2025, 6, 2, tzinfo=timezone.utc))
        n3 = await make_news(db_session, src.id, published_at=datetime(2025, 6, 1, tzinfo=timezone.utc))

        r1 = await client.get(f"{BASE}/?limit=2&offset=0")
        assert [i["id"] for i in r1.json()["items"]] == [n1.id, n2.id]
        assert r1.json()["total"] == 3

        r2 = await client.get(f"{BASE}/?limit=2&offset=2")
        assert [i["id"] for i in r2.json()["items"]] == [n3.id]

    async def test_max_limit_100(self, client: AsyncClient, db_session: AsyncSession):
        r = await client.get(f"{BASE}/?limit=200")
        assert r.status_code == 422
