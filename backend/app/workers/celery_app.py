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
    "app.workers.tasks.fetch_sources":              {"queue": "parsing"},
    "app.workers.tasks.fetch_telegram_channel":     {"queue": "parsing"},
    "app.workers.tasks.fetch_website":              {"queue": "parsing"},
    "app.workers.tasks.process_news_ai":            {"queue": "ai"},
    "app.workers.tasks.send_notifications":          {"queue": "notifications"},
    "app.workers.tasks.send_single_notification":   {"queue": "notifications"},
    "app.workers.tasks.update_topic_preferences":   {"queue": "preferences"},
    "app.workers.tasks.reprocess_news_ai":           {"queue": "ai"},
    "app.workers.tasks.index_news_vector":          {"queue": "ai"},
}

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_transport_options={"visibility_timeout": 60 * 60},
)

celery_app.conf.beat_schedule = {
    "fetch-all-sources": {
        "task": "app.workers.tasks.fetch_sources",
        "schedule": crontab(minute="*/15"),  # every 15 min
        "options": {"expires": 14 * 60},
    },
    "recover-pending-ai": {
        "task": "app.workers.tasks.reprocess_news_ai",
        "schedule": crontab(minute="*/10"),
        "kwargs": {"batch_size": 100},
        "options": {"expires": 9 * 60},
    },
}
