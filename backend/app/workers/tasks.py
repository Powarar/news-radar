import logging
from collections import defaultdict

import httpx
import redis as redis_sync
from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.news import NewsItem
from app.models.source import Source, SourceType
from app.models.user import User, UserTopicPreference
from app.services.ai.importance import score_importance
from app.services.ai.pipeline import process as ai_process
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url_sync, poolclass=NullPool)
SyncSessionLocal = sessionmaker(engine)
sync_redis = redis_sync.Redis.from_url(settings.redis_url)

_tg_client: httpx.Client | None = None


class TelegramSendError(RuntimeError):
    """Telegram Bot API rejected a notification."""


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
    from datetime import datetime, timedelta, timezone
    if source.last_fetched_at is None:
        return False
    interval = timedelta(minutes=source.fetch_interval_minutes)
    return datetime.now(timezone.utc) - source.last_fetched_at < interval


# ─────────────────────────────────────────────────────────────
#  fetch_telegram_channel — парсит один Telegram-канал
# ─────────────────────────────────────────────────────────────

@celery_app.task(
    name="app.workers.tasks.fetch_telegram_channel",
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def fetch_telegram_channel(source_id: int):
    """
    Парсит публичный Telegram-канал через t.me/s/<channel>.
    Сохраняет только новые посты (проверяет по url).
    """
    from datetime import datetime, timezone

    from app.models.news import NewsItem
    from app.services.parser.telegram import parse_channel

    with SyncSessionLocal() as session:
        # Row lock serializes overlapping tasks for the same source.
        source = session.get(Source, source_id, with_for_update=True)
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

        pending_ai_ids: list[int] = []
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
                ai_status="pending",
            )
            session.add(news)
            session.flush()
            pending_ai_ids.append(news.id)
            existing_urls.add(post["url"])

        source.last_fetched_at = datetime.now(timezone.utc)
        session.commit()

        # Dispatch only after commit so workers can always see the new rows.
        for news_id in pending_ai_ids:
            process_news_ai.delay(news_id)

        return f"Saved {len(pending_ai_ids)} new posts from @{channel}"


# ─────────────────────────────────────────────────────────────
#  fetch_website — парсит сайт или RSS-ленту
# ─────────────────────────────────────────────────────────────

@celery_app.task(
    name="app.workers.tasks.fetch_website",
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def fetch_website(source_id: int):
    """
    Парсит сайт: сначала ищет RSS,
    при неудаче — скрапит HTML страницу.
    """
    from datetime import datetime, timezone

    from app.models.news import NewsItem
    from app.services.parser.web import fetch_site

    with SyncSessionLocal() as session:
        source = session.get(Source, source_id, with_for_update=True)
        if not source or not source.is_active:
            return

        if _should_skip(source):
            return f"Skipped {source.url} — fetched recently"

        items = fetch_site(source.url)

        incoming_urls = [i["url"] for i in items if i.get("url")]
        existing_urls = set(session.execute(
            select(NewsItem.url).where(NewsItem.url.in_(incoming_urls))
        ).scalars().all()) if incoming_urls else set()

        pending_ai_ids: list[int] = []
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
                ai_status="pending",
            )
            session.add(news)
            session.flush()
            pending_ai_ids.append(news.id)
            existing_urls.add(item["url"])

        source.last_fetched_at = datetime.now(timezone.utc)
        session.commit()

        for news_id in pending_ai_ids:
            process_news_ai.delay(news_id)

        return f"Saved {len(pending_ai_ids)} new items from {source.url}"


# ─────────────────────────────────────────────────────────────
#  process_news_ai — AI обработка (топики, важность, саммари)
# ─────────────────────────────────────────────────────────────


@celery_app.task(
    name="app.workers.tasks.process_news_ai",
    bind=True,
    # Two retries plus the initial execution: at most three full task runs.
    max_retries=2,
    rate_limit="15/m",
)
def process_news_ai(self, news_id: int, force: bool = False, notify: bool = True):
    """Classify topics and generate a summary, retrying failed Groq runs."""
    with SyncSessionLocal() as session:
        # Late acknowledgement permits redelivery. Locking the row makes two
        # concurrent deliveries serialize; the second sees the committed status.
        news = session.scalar(
            select(NewsItem)
            .where(NewsItem.id == news_id)
            .with_for_update()
        )
        if not news:
            return
        if not force and news.ai_status == "ok":
            return f"News {news_id} already processed"

        text = (news.title or "") + " " + news.body

        topics, summary, status = ai_process(text, news_id=news_id)

        # The pipeline deliberately converts provider/network failures into a
        # status instead of raising. Without an explicit task retry Celery sees
        # that as success, leaving the item without a summary forever.
        if status == "failed" and self.request.retries < self.max_retries:
            countdown = 30 * (2 ** self.request.retries)
            logger.warning(
                "AI processing failed for news_id=%d; retry %d/%d in %ds",
                news_id,
                self.request.retries + 1,
                self.max_retries,
                countdown,
            )
            raise self.retry(countdown=countdown)

        if not topics:
            logger.warning("No topics for news_id=%d | text=%.120s", news_id, text[:120])

        news.topics = topics if topics else None
        news.summary = summary
        news.ai_status = status

        # Load recent classified news for percentile-based importance
        recent = session.execute(
            select(NewsItem.topics)
            .where(NewsItem.topics.isnot(None), NewsItem.id != news_id)
            .order_by(NewsItem.created_at.desc())
            .limit(200)
        ).scalars().all()
        history = [r for r in recent if r]

        news.importance_score = score_importance(topics, history)
        session.commit()

        if status == "ok":
            index_news_vector.delay(news_id)

        if topics and notify:
            send_notifications.delay(news_id)


# ─────────────────────────────────────────────────────────────
#  index_news_vector — векторизация и сохранение в Qdrant
# ─────────────────────────────────────────────────────────────

@celery_app.task(
    name="app.workers.tasks.index_news_vector",
    rate_limit="1/s",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def index_news_vector(news_id: int):
    """Генерация эмбеддинга новости и индексирование в Qdrant по очереди (Redis Lock)."""
    lock = sync_redis.lock("lock:news_embedding", timeout=60, blocking_timeout=15)
    acquired = False
    try:
        acquired = lock.acquire()
        if not acquired:
            logger.warning("Could not acquire embedding lock for news_id=%d, retrying", news_id)
            raise index_news_vector.retry(countdown=5)

        from app.services.ai.embedding import index_news_to_qdrant
        with SyncSessionLocal() as session:
            news = session.get(NewsItem, news_id)
            if not news or news.ai_status != "ok":
                return

            title = news.title or ""
            text = news.body or ""
            published_timestamp = int(
                (news.published_at or news.created_at).timestamp()
            )
            index_news_to_qdrant(news.id, title, text, news.summary, published_timestamp)
    finally:
        if acquired:
            try:
                lock.release()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────
#  reprocess_news_ai — backfill: re-run AI on items missing summary
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.reprocess_news_ai")
def reprocess_news_ai(batch_size: int = 100, include_failed: bool = False):
    """
    Recover AI work that was committed but not dispatched.

    Set include_failed=True for a deliberate backfill after an outage or model
    upgrade. The periodic recovery job only picks stale "pending" rows so it
    cannot continuously retry the full historical dataset.

    Trigger manually:
        celery -A app.workers.celery_app call app.workers.tasks.reprocess_news_ai
    """
    with SyncSessionLocal() as session:
        from datetime import datetime, timedelta, timezone

        stale_pending_cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
        recovery_condition = (
            (NewsItem.ai_status == "pending")
            & (NewsItem.created_at < stale_pending_cutoff)
        )
        if include_failed:
            recovery_condition = or_(
                recovery_condition,
                NewsItem.ai_status.is_(None),
                NewsItem.ai_status == "failed",
            )

        rows = session.execute(
            select(NewsItem.id, NewsItem.ai_status)
            .where(recovery_condition)
            .order_by(NewsItem.id.desc())
            .limit(batch_size)
        ).all()

        for news_id, ai_status in rows:
            # Historical NULL/failed rows must not produce a burst of old
            # Telegram notifications when manually backfilled.
            process_news_ai.apply_async(
                args=[news_id],
                kwargs={"notify": not include_failed and ai_status == "pending"},
            )

        logger.info("reprocess_news_ai: dispatched %d items", len(rows))
        return f"Dispatched {len(rows)} items for reprocessing"


# ─────────────────────────────────────────────────────────────
#  update_topic_preferences — обновляет веса топиков юзера
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.update_topic_preferences")
def update_topic_preferences(user_id: int, news_id: int, preference_delta: float | str):
    with SyncSessionLocal() as session:
        # Multiple reaction tasks for one user may arrive concurrently.
        # Lock the user row before the read/modify/write preference sequence.
        if session.scalar(
            select(User.id)
            .where(User.id == user_id)
            .with_for_update()
        ) is None:
            return

        item = session.scalar(select(NewsItem).where(NewsItem.id == news_id))
        if not item or not item.topics:
            return

        news_topics = item.topics  # {"politics": 0.9, "military": 0.6}
        # Accept legacy queued payloads during a rolling deployment.
        if isinstance(preference_delta, str):
            preference_delta = 0.1 if preference_delta == "like" else -0.1

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
            pref.weight = max(
                0.0,
                min(1.0, pref.weight + preference_delta * score),
            )

        session.commit()


@celery_app.task(name="app.workers.tasks.send_notifications")
def send_notifications(news_item_id: int):
    """Fan-out: find matched users and dispatch one task per user."""
    from datetime import datetime, timedelta, timezone

    with SyncSessionLocal() as session:
        news = session.scalar(select(NewsItem).where(NewsItem.id == news_item_id))
        if not news or not news.topics:
            return

        news_time = news.published_at or news.created_at
        if news_time and datetime.now(timezone.utc) - news_time > timedelta(hours=2):
            logger.info("Skipping notification for old news_id=%d", news_item_id)
            return

        news_topics = news.topics

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
        raise TelegramSendError(f"TG rate limit, retry after {retry_after}s")

    if resp.status_code != 200:
        raise TelegramSendError(f"TG sendMessage failed: {resp.status_code} {resp.text}")
