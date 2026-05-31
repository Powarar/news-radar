#!/usr/bin/env python3
"""
Скрипт для добавления источников (Telegram-каналов и RSS) в БД.

Запуск:
  docker compose exec backend python /app/scripts/seed_sources.py

Idempotent — повторный запуск не создаёт дубликатов.
"""
import sys
sys.path.insert(0, "/app")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User  # noqa: F401
from app.models.news import NewsItem  # noqa: F401
from app.models.source import Source, SourceType

import json

def tg(name, username, topics=None, country="RU"):
    return {
        "name": name,
        "url": f"https://t.me/{username}",
        "type": SourceType.telegram,
        "language": "ru",
        "country": country,
        "topics": json.dumps(topics) if topics else None,
    }

def rss(name, url, language="ru", topics=None, country=None):
    return {
        "name": name,
        "url": url,
        "type": SourceType.rss,
        "language": language,
        "country": country,
        "topics": json.dumps(topics) if topics else None,
    }

SOURCES = [
    # ── Общие новости ──────────────────────────────────────────────────────────
    tg("Meduza",               "meduzalive",       ["politics"]),
    tg("BBC Русская служба",   "bbcrussian",       ["politics"]),
    tg("РБК",                  "rbc_news",         ["politics", "business"]),
    tg("Коммерсантъ",          "kommersant",       ["politics", "business"]),
    tg("Lenta.ru",             "lentaru",          ["politics"]),
    tg("Настоящее Время",      "currenttime",      ["politics"]),
    tg("Дождь",                "tvrain",           ["politics"]),
    tg("Фонтанка.ру",          "fontanka_news",    ["politics"]),
    tg("Новая газета Европа",  "novaya_europe",    ["politics"]),
    tg("ТАСС",                 "tass_agency",      ["politics"]),

    # ── Технологии / IT ────────────────────────────────────────────────────────
    tg("Хабр",                 "habr_tg",          ["technology"]),
    tg("VC.ru",                "vcnews",           ["technology", "business"]),
    tg("Rusbase",              "rusbase",          ["technology", "business"]),
    tg("3DNews",               "tdnevs",           ["technology"]),
    tg("iXBT",                 "ixbt_news",        ["technology"]),

    # ── Бизнес / Финансы ───────────────────────────────────────────────────────
    tg("Ведомости",            "vedomosti",        ["business"]),
    tg("Forbes Russia",        "forbesrussia",     ["business"]),
    tg("Банки.ру",             "bankiru",          ["business"]),

    # ── Наука ──────────────────────────────────────────────────────────────────
    tg("Naked Science",        "naked_science",    ["science"]),
    tg("N+1",                  "nplus1",           ["science", "technology"]),
    tg("Кот Шрёдингера",       "kot_schroedingers",["science"]),

    # ── Здоровье ───────────────────────────────────────────────────────────────
    tg("Медвестник",           "medvestnik_ru",    ["health"]),

    # ── Спорт ──────────────────────────────────────────────────────────────────
    tg("Матч ТВ",              "matchtv",          ["sports"]),
    tg("Чемпионат",            "championat",       ["sports"]),

    # ── Культура ───────────────────────────────────────────────────────────────
    tg("Афиша",                "afisha",           ["culture"]),
    tg("Кино-Театр.ру",        "kinoteatr_ru",     ["culture"]),

    # ── Военная аналитика ──────────────────────────────────────────────────────
    tg("Рыбарь",               "rybar",            ["military"]),

    # ── RSS ────────────────────────────────────────────────────────────────────
    rss("Meduza RSS",          "https://meduza.io/rss/all",                        topics=["politics"]),
    rss("BBC Русская RSS",     "https://feeds.bbci.co.uk/russian/rss.xml",         topics=["politics"]),
    rss("Lenta.ru RSS",        "https://lenta.ru/rss/news",                        topics=["politics"]),
    rss("Хабр (лучшее)",       "https://habr.com/ru/rss/best/daily/",              topics=["technology"]),
    rss("N+1 RSS",             "https://nplus1.ru/rss",                            topics=["science", "technology"]),
    rss("TechCrunch RSS",      "https://techcrunch.com/feed/",   language="en",    topics=["technology"]),
    rss("Meduza EN",           "https://meduza.io/rss/en/all",   language="en",    topics=["politics"]),
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
            country=s.get("country"),
            topics=s.get("topics"),
            is_active=True,
        )
        session.add(source)
        added += 1
        print(f"  добавлен: {s['name']}")
    session.commit()

print(f"\nГотово! Добавлено {added} источников.")
