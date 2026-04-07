from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.fetch_sources")
def fetch_sources():
    """Fetch new articles from all active sources (TG + web)."""
    # TODO: query active sources, dispatch per-source fetch tasks
    pass


@celery_app.task(name="app.workers.tasks.fetch_telegram_channel")
def fetch_telegram_channel(source_id: int):
    """Parse new messages from a Telegram channel."""
    # TODO: Telethon client, save new NewsItem rows
    pass


@celery_app.task(name="app.workers.tasks.fetch_website")
def fetch_website(source_id: int):
    """Scrape / parse RSS feed from a website."""
    # TODO: httpx + BeautifulSoup / feedparser
    pass


@celery_app.task(name="app.workers.tasks.process_news_ai")
def process_news_ai(news_item_id: int):
    """Classify topics, score importance, generate summary via HuggingFace."""
    # TODO: HF Inference API calls → update NewsItem row
    pass


@celery_app.task(name="app.workers.tasks.send_notifications")
def send_notifications(news_item_id: int):
    """Push relevant news to matched users via TG bot."""
    # TODO: match users by preferences, send via aiogram
    pass
