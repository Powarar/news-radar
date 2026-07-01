import json
import logging

from collections import defaultdict

import httpx
from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.news import NewsItem  # noqa: F401
from app.models.source import Source, SourceType
from app.models.user import User, UserTopicPreference  # noqa: F401
from app.workers.celery_app import celery_app
from app.services.ai.classifier import classify
from app.services.ai.importance import score_importance
from app.services.ai.summarizer import summarize

logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url_sync, poolclass=NullPool)
SyncSessionLocal = sessionmaker(engine)

_tg_client: httpx.Client | None = None


def _get_tg_client() -> httpx.Client:
    global _tg_client
    if _tg_client is None or _tg_client.is_closed:
        _tg_client = httpx.Client(timeout=10)
    return _tg_client


# ─────────────────────────────────────────────────────────────
#  fetch_sources — запускается по расписанию каждые 15 минут
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.fetch_sources")
def fetch_sources():
    """
    Смотрит все активные источники в БД и запускает
    отдельную задачу для каждого.
    """

    with SyncSessionLocal() as session:
        sources = session.execute(
            select(Source).where(Source.is_active)
        ).scalars().all()

        for source in sources:
            if source.type == SourceType.telegram:
                fetch_telegram_channel.delay(source.id)
            elif source.type in (SourceType.website, SourceType.rss):
                fetch_website.delay(source.id)


# ─────────────────────────────────────────────────────────────
#  _should_skip — проверяем не слишком ли рано снова парсить
# ─────────────────────────────────────────────────────────────

def _should_skip(source) -> bool:
    """
    Возвращает True если источник парсили недавно.

    Зачем: Beat запускает fetch_sources каждые 15 минут,
    но у разных источников разный fetch_interval_minutes.
    Например канал который обновляется раз в час — не нужно парсить каждые 15 минут.
    """
    from datetime import datetime, timezone, timedelta
    if source.last_fetched_at is None:
        return False
    interval = timedelta(minutes=source.fetch_interval_minutes)
    return datetime.now(timezone.utc) - source.last_fetched_at < interval


# ─────────────────────────────────────────────────────────────
#  fetch_telegram_channel — парсит один Telegram-канал
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.fetch_telegram_channel")
def fetch_telegram_channel(source_id: int):
    """
    Парсит публичный Telegram-канал через t.me/s/<channel>.
    Сохраняет только новые посты (проверяет по url).
    """
    from datetime import datetime, timezone
    from app.models.news import NewsItem
    from app.services.parser.telegram import parse_channel

    with SyncSessionLocal() as session:
        source = session.get(Source, source_id)
        if not source or not source.is_active:
            return

        if _should_skip(source):
            return f"Skipped @{source.url} — fetched recently"

        channel = source.url.rstrip("/").split("/")[-1]

        try:
            posts = parse_channel(channel, limit=30)
        except ValueError as e:
            source.is_active = False
            session.commit()
            return str(e)

        incoming_urls = [p["url"] for p in posts]
        existing_urls = set(session.execute(
            select(NewsItem.url).where(NewsItem.url.in_(incoming_urls))
        ).scalars().all())

        saved = 0
        for post in posts:
            if post["url"] in existing_urls:
                continue

            # Парсим дату
            published_at = None
            if post["published_at"]:
                try:
                    published_at = datetime.fromisoformat(post["published_at"])
                except ValueError:
                    pass

            news = NewsItem(
                source_id=source_id,
                body=post["text"],
                url=post["url"],
                image_url=post["image_url"],
                language=source.language,
                published_at=published_at,
            )
            session.add(news)
            session.flush()
            process_news_ai.delay(news.id)
            saved += 1

        source.last_fetched_at = datetime.now(timezone.utc)
        session.commit()

        return f"Saved {saved} new posts from @{channel}"


# ─────────────────────────────────────────────────────────────
#  fetch_website — парсит сайт или RSS-ленту
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.fetch_website")
def fetch_website(source_id: int):
    """
    Парсит сайт: сначала ищет RSS,
    при неудаче — скрапит HTML страницу.
    """
    from datetime import datetime, timezone
    from app.models.news import NewsItem
    from app.services.parser.web import fetch_site

    with SyncSessionLocal() as session:
        source = session.get(Source, source_id)
        if not source or not source.is_active:
            return

        if _should_skip(source):
            return f"Skipped {source.url} — fetched recently"

        items = fetch_site(source.url)

        incoming_urls = [i["url"] for i in items if i.get("url")]
        existing_urls = set(session.execute(
            select(NewsItem.url).where(NewsItem.url.in_(incoming_urls))
        ).scalars().all()) if incoming_urls else set()

        saved = 0
        for item in items:
            if not item.get("url") or item["url"] in existing_urls:
                continue

            published_at = None
            if item.get("published_at"):
                try:
                    published_at = datetime.fromisoformat(item["published_at"])
                except ValueError:
                    pass

            news = NewsItem(
                source_id=source_id,
                title=item.get("title"),
                body=item["text"],
                url=item["url"],
                image_url=item.get("image_url"),
                language=source.language,
                published_at=published_at,
            )
            session.add(news)
            session.flush()
            process_news_ai.delay(news.id)
            saved += 1

        source.last_fetched_at = datetime.now(timezone.utc)
        session.commit()

        return f"Saved {saved} new items from {source.url}"


# ─────────────────────────────────────────────────────────────
#  process_news_ai — AI обработка (топики, важность, саммари)
# ─────────────────────────────────────────────────────────────


@celery_app.task(
    name="app.workers.tasks.process_news_ai",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_news_ai(news_id: int):
    """Classify topics and generate summary via Groq (keyword fallback if unavailable)."""
    with SyncSessionLocal() as session:
        news = session.scalar(select(NewsItem).where(NewsItem.id == news_id))
        if not news:
            return
        text = (news.title or "") + " " + news.body

        topics = classify(text)        # never raises — falls back to keywords
        summary, status = summarize(text, news_id=news_id)  # (summary|None, "ok"|"skipped"|"failed")

        if not topics:
            logger.warning("No topics for news_id=%d | text=%.120s", news_id, text[:120])

        news.topics = json.dumps(topics) if topics else None
        news.summary = summary
        news.ai_status = status
        news.importance_score = score_importance(topics)
        session.commit()

        if topics:
            send_notifications.delay(news_id)


# ─────────────────────────────────────────────────────────────
#  reprocess_news_ai — backfill: re-run AI on items missing summary
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.reprocess_news_ai")
def reprocess_news_ai(batch_size: int = 100):
    """
    Find news items where summary IS NULL (or ai_status IS NULL / 'failed')
    and re-dispatch process_news_ai for each. Use after seeding data,
    Groq outages, or model upgrades.

    Trigger manually:
        celery -A app.workers.celery_app call app.workers.tasks.reprocess_news_ai
    """
    with SyncSessionLocal() as session:
        rows = session.execute(
            select(NewsItem.id)
            .where(
                or_(
                    NewsItem.summary.is_(None),
                    NewsItem.ai_status.is_(None),
                    NewsItem.ai_status == "failed",
                )
            )
            .order_by(NewsItem.id.desc())
            .limit(batch_size)
        ).scalars().all()

        for news_id in rows:
            process_news_ai.delay(news_id)

        logger.info("reprocess_news_ai: dispatched %d items", len(rows))
        return f"Dispatched {len(rows)} items for reprocessing"


# ─────────────────────────────────────────────────────────────
#  update_topic_preferences — обновляет веса топиков юзера
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.update_topic_preferences")
def update_topic_preferences(user_id: int, news_id: int, reaction: str):
    with SyncSessionLocal() as session:
        item = session.scalar(select(NewsItem).where(NewsItem.id == news_id))
        if not item or not item.topics:
            return

        news_topics = json.loads(item.topics)  # {"politics": 0.9, "military": 0.6}
        delta = 0.1 if reaction == "like" else -0.1

        topics_to_update = [t for t, s in news_topics.items() if s >= 0.3]

        existing = session.scalars(
            select(UserTopicPreference).where(
                UserTopicPreference.user_id == user_id,
                UserTopicPreference.topic.in_(topics_to_update),
            )
        ).all()
        prefs_map = {p.topic: p for p in existing}

        for topic, score in news_topics.items():
            if score < 0.3:
                continue
            pref = prefs_map.get(topic)
            if not pref:
                pref = UserTopicPreference(user_id=user_id, topic=topic, weight=0.5)
                session.add(pref)
            pref.weight = max(0.0, min(1.0, pref.weight + delta * score))

        session.commit()


@celery_app.task(name="app.workers.tasks.send_notifications")
def send_notifications(news_item_id: int):
    """Fan-out: find matched users and dispatch one task per user."""
    from datetime import datetime, timezone, timedelta

    with SyncSessionLocal() as session:
        news = session.scalar(select(NewsItem).where(NewsItem.id == news_item_id))
        if not news or not news.topics:
            return

        news_time = news.published_at or news.created_at
        if news_time and datetime.now(timezone.utc) - news_time > timedelta(hours=2):
            logger.info("Skipping notification for old news_id=%d", news_item_id)
            return

        news_topics = json.loads(news.topics)

        if not settings.telegram_bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, skipping notifications")
            return

        all_users = session.execute(
            select(User.id, User.telegram_id)
            .where(
                User.telegram_id.isnot(None),
                User.notifications_enabled,
            )
        ).all()

        if not all_users:
            logger.info("No Telegram users with notifications enabled")
            return

        # Build message once — same for all users
        title = news.title or ""
        if not title and news.body:
            title = news.body[:160].rstrip()
            if len(news.body) > 160:
                title += "…"
        title = title or "Без заголовка"

        topics_str = ", ".join(
            f"{topic}: {score:.0%}" for topic, score in
            sorted(news_topics.items(), key=lambda x: x[1], reverse=True)[:3]
        )
        # Show summary whenever it exists — TG posts use body as title, summary is still useful
        summary_line = f"\n\n{news.summary}" if news.summary else ""
        url_line = f"\n\nПодробнее: {news.url}" if news.url else ""
        text = (
            f"<b>{title}</b>\n"
            f"Темы: {topics_str}{summary_line}{url_line}"
        )

        user_ids = [u.id for u in all_users]
        prefs_rows = session.execute(
            select(UserTopicPreference.user_id, UserTopicPreference.topic)
            .where(
                UserTopicPreference.user_id.in_(user_ids),
                UserTopicPreference.weight > 0,
            )
        ).all()

        user_topics: dict[int, list[str]] = defaultdict(list)
        for user_id, topic in prefs_rows:
            user_topics[user_id].append(topic)

        dispatched = 0
        for user_id, telegram_id in all_users:
            prefs = user_topics.get(user_id)
            if prefs:
                matching = [t for t in prefs if t in news_topics and news_topics[t] > 0.2]
                if not matching:
                    continue
            # No preferences yet → send everything (new subscriber)
            send_single_notification.delay(telegram_id, text, news_item_id)
            dispatched += 1

        logger.info("Dispatched %d notifications for news_id=%d", dispatched, news_item_id)


@celery_app.task(
    name="app.workers.tasks.send_single_notification",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    rate_limit="6/s",
)
def send_single_notification(telegram_id: str, text: str, news_item_id: int):
    """Send one Telegram message to one user."""
    bot_token = settings.telegram_bot_token
    keyboard = {
        "inline_keyboard": [[
            {"text": "↑ 0", "callback_data": f"like:{news_item_id}"},
            {"text": "↓ 0", "callback_data": f"dislike:{news_item_id}"},
            {"text": "✖", "callback_data": f"blacklist:{news_item_id}"},
        ]]
    }

    resp = _get_tg_client().post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": telegram_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": keyboard,
            },
        )

    if resp.status_code == 429:
        retry_after = resp.json().get("parameters", {}).get("retry_after", 10)
        raise Exception(f"TG rate limit, retry after {retry_after}s")

    if resp.status_code != 200:
        raise Exception(f"TG sendMessage failed: {resp.status_code} {resp.text}")
