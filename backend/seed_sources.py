"""
Скрипт для добавления тестовых источников (Telegram-каналов) в БД.

Запуск:
  docker compose exec backend python seed_sources.py

Это нужно сделать один раз. После этого Celery будет
автоматически парсить эти каналы каждые 15 минут.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User  # noqa: F401
from app.models.news import NewsItem  # noqa: F401
from app.models.source import Source, SourceType

CHANNELS = [
    {"name": "Meduza", "url": "https://t.me/meduzalive", "language": "ru"},
    {"name": "BBC News Русская служба", "url": "https://t.me/bbcrussian", "language": "ru"},
    {"name": "РБК", "url": "https://t.me/rbc_news", "language": "ru"},
    {"name": "Медуза (Англ)", "url": "https://t.me/meduza_en", "language": "en"},
]

engine = create_engine(settings.database_url_sync)

with Session(engine) as session:
    added = 0
    for ch in CHANNELS:
        exists = session.query(Source).filter_by(url=ch["url"]).first()
        if exists:
            print(f"  уже есть: {ch['name']}")
            continue
        source = Source(
            name=ch["name"],
            url=ch["url"],
            type=SourceType.telegram,
            language=ch["language"],
            is_active=True,
        )
        session.add(source)
        added += 1
        print(f"  добавлен: {ch['name']}")
    session.commit()

print(f"\nГотово! Добавлено {added} источников.")
print("Теперь запусти: docker compose exec backend celery -A app.workers.celery_app worker -Q parsing -l info")
