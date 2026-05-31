import json
import logging

from collections import defaultdict

from sqlalchemy import and_, create_engine, select
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

        saved = 0
        for post in posts:
            exists = session.execute(
                select(NewsItem.id).where(NewsItem.url == post["url"])
            ).scalar_one_or_none()
            if exists:
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

        saved = 0
        for item in items:
            if not item.get("url"):
                continue

            exists = session.execute(
                select(NewsItem.id).where(NewsItem.url == item["url"])
            ).scalar_one_or_none()
            if exists:
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


@celery_app.task(name="app.workers.tasks.process_news_ai", bind=True, max_retries=3)
def process_news_ai(self, news_id: int):
    """Classify topics, score importance, generate summary via HuggingFace."""
    with SyncSessionLocal() as session:
        news = session.scalar(select(NewsItem).where(NewsItem.id == news_id))
        if not news:
            return
        text = (news.title or "") + " " + news.body

        topics: dict = {}
        summary: str | None = None

        try:
            topics = classify(text)
        except Exception:
            logger.exception("classify failed for news_id=%d", news_id)

        try:
            summary = summarize(text)
        except Exception:
            logger.exception("summarize failed for news_id=%d", news_id)

        news.topics = json.dumps(topics)
        news.summary = summary
        news.importance_score = score_importance(topics)
        session.commit()

        if not topics:
            countdown = 30 * (2 ** self.request.retries)  # 30s, 60s, 120s
            logger.warning("classify returned nothing for news_id=%d, retry %d in %ds",
                           news_id, self.request.retries + 1, countdown)
            raise self.retry(countdown=countdown)

        send_notifications.delay(news_id)

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

        for topic, score in news_topics.items():
            if score < 0.3:
                continue

            pref = session.scalar(
                select(UserTopicPreference).where(
                    UserTopicPreference.user_id == user_id,
                    UserTopicPreference.topic == topic,
                )
            )
            if not pref:
                pref = UserTopicPreference(user_id=user_id, topic=topic, weight=0.5)
                session.add(pref)

            pref.weight = max(0.0, min(1.0, pref.weight + delta * score))

        session.commit()


@celery_app.task(name="app.workers.tasks.send_notifications")
def send_notifications(news_item_id: int):
    """Push relevant news to matched users via TG bot."""
    import httpx

    with SyncSessionLocal() as session:
        news = session.scalar(select(NewsItem).where(NewsItem.id == news_item_id))
        if not news or not news.topics:
            return

        news_topics = json.loads(news.topics)

        bot_token = settings.telegram_bot_token
        if not bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, skipping notifications")
            return

        # One query: all telegram users joined with their topic preferences
        rows = session.execute(
            select(User.id, User.telegram_id, UserTopicPreference.topic)
            .join(UserTopicPreference, and_(
                UserTopicPreference.user_id == User.id,
                UserTopicPreference.weight > 0,
            ))
            .where(
                User.telegram_id.isnot(None),
                User.notifications_enabled,
            )
        ).all()

        if not rows:
            logger.info("No Telegram users with preferences found")
            return

        # Group topics by user
        user_prefs: dict[int, tuple[str, list[str]]] = defaultdict(lambda: ("", []))
        for user_id, telegram_id, topic in rows:
            _, topics = user_prefs[user_id]
            user_prefs[user_id] = (telegram_id, topics + [topic])

        # Build message
        title = news.title or "Без заголовка"
        topics_str = ", ".join(
            f"{topic}: {score:.0%}" for topic, score in
            sorted(news_topics.items(), key=lambda x: x[1], reverse=True)[:3]
        )
        summary_line = f"\n\n{news.summary}" if news.summary else ""
        url_line = f"\n\nПодробнее: {news.url}" if news.url else ""

        text = (
            f"<b>{title}</b>\n"
            f"Темы: {topics_str}{summary_line}{url_line}"
        )

        keyboard = {
            "inline_keyboard": [[
                {"text": "↑ 0", "callback_data": f"like:{news_item_id}"},
                {"text": "↓ 0", "callback_data": f"dislike:{news_item_id}"},
                {"text": "✖", "callback_data": f"blacklist:{news_item_id}"},
            ]]
        }

        with httpx.Client(timeout=10) as client:
            for user_id, (telegram_id, prefs) in user_prefs.items():
                matching = [t for t in prefs if t in news_topics and news_topics[t] > 0.2]
                if not matching:
                    continue

                try:
                    resp = client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={
                            "chat_id": telegram_id,
                            "text": text,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True,
                            "reply_markup": keyboard,
                        },
                    )
                    if resp.status_code != 200:
                        logger.warning(
                            "Failed to send notification to user_id=%d telegram_id=%s: %s",
                            user_id, telegram_id, resp.text,
                        )
                except Exception:
                    logger.exception("Error sending notification to user_id=%d", user_id)
