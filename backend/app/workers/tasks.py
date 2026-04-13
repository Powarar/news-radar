from app.workers.celery_app import celery_app

@celery_app.task(name="app.workers.tasks.fetch_sources")
def fetch_sources():
    """
    Смотрит все активные источники в БД и запускает
    отдельную задачу для каждого.
    """

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.core.config import settings
    from app.models.news import NewsItem  # noqa: F401
    from app.models.source import Source
    from app.models.user import User  # noqa: F401
    engine = create_engine(settings.database_url_sync)

    with Session(engine) as session:
        sources = session.execute(
            select(Source).where(Source.is_active == True)
        ).scalars().all()

        for source in sources:
            if source.type == "telegram":
                fetch_telegram_channel.delay(source.id)


# ─────────────────────────────────────────────────────────────
#  fetch_telegram_channel — парсит один Telegram-канал
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.fetch_telegram_channel")
def fetch_telegram_channel(source_id: int):
    """
    Парсит публичный Telegram-канал через t.me/s/<channel>
    (это веб-версия канала, доступна без API-ключей).

    Сохраняет только новые посты (проверяет по url, который уникален).
    """
    import httpx
    from bs4 import BeautifulSoup
    from datetime import datetime, timezone
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.core.config import settings
    from app.models.news import NewsItem
    from app.models.source import Source
    from app.models.user import User  # noqa: F401 — нужен для разрешения связи NewsReaction → User

    engine = create_engine(settings.database_url_sync)

    with Session(engine) as session:
        source = session.get(Source, source_id)
        if not source or not source.is_active:
            return

        channel = source.url.rstrip("/").split("/")[-1]

        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            r = httpx.get(f"https://t.me/s/{channel}", headers=headers, follow_redirects=True, timeout=15)
        except Exception:
            return
        
        soup = BeautifulSoup(r.text, "html.parser")
        messages = soup.find_all("div", class_="tgme_widget_message_wrap")

        saved = 0
        for msg in messages:
            text_el = msg.find("div", class_="tgme_widget_message_text")
            time_el = msg.find("time")
            link_el = msg.find("a", class_="tgme_widget_message_date")

            text = text_el.get_text(separator=" ", strip=True) if text_el else None
            link = link_el.get("href") if link_el else None

            if not text or not link:
                continue  

            exists = session.execute(
                select(NewsItem.id).where(NewsItem.url == link)
            ).scalar_one_or_none()

            if exists:
                continue

            published_at = None
            if time_el and time_el.get("datetime"):
                try:
                    published_at = datetime.fromisoformat(time_el["datetime"])
                except ValueError:
                    pass

            news = NewsItem(
                source_id=source_id,
                body=text,
                url=link,
                language=source.language,
                published_at=published_at,
            )
            session.add(news)
            saved += 1

        session.commit()

        # Обновляем время последнего парсинга
        source.last_fetched_at = datetime.now(timezone.utc)
        session.commit()

        return f"Saved {saved} new posts from @{channel}"


# ─────────────────────────────────────────────────────────────
#  Остальные задачи — заготовки на будущее
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.fetch_website")
def fetch_website(source_id: int):
    """Scrape / parse RSS feed from a website."""
    pass


@celery_app.task(name="app.workers.tasks.process_news_ai")
def process_news_ai(news_item_id: int):
    """Classify topics, score importance, generate summary via HuggingFace."""
    pass


@celery_app.task(name="app.workers.tasks.send_notifications")
def send_notifications(news_item_id: int):
    """Push relevant news to matched users via TG bot."""
    pass
