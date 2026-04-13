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

SOURCES = [
    # Telegram каналы
    {"name": "Meduza",             "url": "https://t.me/meduzalive",  "type": SourceType.telegram, "language": "ru"},
    {"name": "BBC Русская служба", "url": "https://t.me/bbcrussian",  "type": SourceType.telegram, "language": "ru"},
    {"name": "РБК",                "url": "https://t.me/rbc_news",    "type": SourceType.telegram, "language": "ru"},
    {"name": "Meduza EN",          "url": "https://t.me/meduza_en",   "type": SourceType.telegram, "language": "en"},
    # RSS ленты
    {"name": "Meduza RSS",         "url": "https://meduza.io/rss/all","type": SourceType.rss,      "language": "ru"},
    {"name": "BBC RSS (ru)",       "url": "https://feeds.bbci.co.uk/russian/rss.xml", "type": SourceType.rss, "language": "ru"},
    {"name": "Lenta.ru RSS",       "url": "https://lenta.ru/rss/news","type": SourceType.rss,      "language": "ru"},
    {"name": "TechCrunch RSS",     "url": "https://techcrunch.com/feed/","type": SourceType.rss,   "language": "en"},
]

engine = create_engine(settings.database_url_sync)

with Session(engine) as session:
    added = 0
    for s in SOURCES:
        exists = session.query(Source).filter_by(url=s["url"]).first()
        if exists:
            print(f"  уже есть: {s['name']}")
            continue
        source = Source(
            name=s["name"],
            url=s["url"],
            type=s["type"],
            language=s["language"],
            is_active=True,
        )
        session.add(source)
        added += 1
        print(f"  добавлен: {s['name']}")
    session.commit()

print(f"\nГотово! Добавлено {added} источников.")
