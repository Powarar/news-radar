from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.news import NewsItem  # noqa: F401
from app.models.source import Source, SourceType
from app.models.user import User  # noqa: F401
from app.workers.celery_app import celery_app

engine = create_engine(settings.database_url_sync)
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
            select(Source).where(Source.is_active == True)
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
            saved += 1

        source.last_fetched_at = datetime.now(timezone.utc)
        session.commit()

        return f"Saved {saved} new items from {source.url}"


# ─────────────────────────────────────────────────────────────
#  process_news_ai — AI обработка (топики, важность, саммари)
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.process_news_ai")
def process_news_ai(news_item_id: int):
    """Classify topics, score importance, generate summary via HuggingFace."""
    # TODO: реализуем когда подключим HuggingFace токен
    pass


@celery_app.task(name="app.workers.tasks.send_notifications")
def send_notifications(news_item_id: int):
    """Push relevant news to matched users via TG bot."""
    # TODO: реализуем когда сделаем бота
    pass
