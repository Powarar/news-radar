from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "news_radar",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.task_routes = {
    "app.workers.tasks.fetch_sources":          {"queue": "parsing"},
    "app.workers.tasks.fetch_telegram_channel": {"queue": "parsing"},
    "app.workers.tasks.fetch_website":          {"queue": "parsing"},
    "app.workers.tasks.process_news_ai":        {"queue": "ai"},
    "app.workers.tasks.send_notifications":     {"queue": "default"},
}

celery_app.conf.beat_schedule = {
    "fetch-all-sources": {
        "task": "app.workers.tasks.fetch_sources",
        "schedule": crontab(minute="*/15"),  # every 15 min
    },
}
