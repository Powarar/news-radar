# CLAUDE.md — News Radar

## Project

Новостной агрегатор с персонализацией через AI. Парсит Telegram-каналы и сайты, классифицирует по темам, суммаризирует, показывает пользователю то что ему интересно.
Stack: FastAPI + PostgreSQL + Celery + Redis + React + aiogram + Docker.

## Architecture

- `backend/` — FastAPI app, all business logic, Celery workers
- `frontend/` — React 18 + TypeScript + Vite PWA
- `bot/` — aiogram 3 Telegram bot (same features as web)
- `nginx/` — reverse proxy, serves frontend, proxies /api to backend
- `docker-compose.yml` — dev environment
- `docker-compose.prod.yml` — production

## Key conventions

- All API routes live under `/api/v1/`
- Auth: JWT (access 24h + refresh 30d) + Google OAuth
- DB access: async SQLAlchemy 2 sessions via `get_db()` dependency
- Background jobs: Celery tasks in `backend/app/workers/tasks.py`
  - queue `parsing` — fetch sources (every 15 min via beat)
  - queue `ai` — classify, summarize, score importance
  - queue `default` — send notifications
- AI via HuggingFace Inference API (not local, not OpenAI):
  - classifier: `facebook/bart-large-mnli`
  - summarizer: `csebuetnlp/mT5_multilingual_XLSum`
- Topics: politics, military, technology, health, science, business, sports, culture, environment
- User preferences stored as `user_topic_preferences` rows with float weight 0.0-1.0
- News importance: `importance_score` float on `news_items` table, computed by `services/ai/importance.py`

## What is NOT done yet (TODO)

- `GET /api/v1/preferences` and `PUT /api/v1/preferences` — stubs
- `GET /api/v1/sources`, `POST /api/v1/sources`, `PATCH /api/v1/sources/{id}/toggle`, `PATCH /api/v1/sources/{id}/blacklist` — stubs
- Importance scoring in `services/ai/importance.py` — returns stub value, needs real formula
- Bot `/settings` and `/sources` handlers — stubs, inline keyboards not done
- Frontend preferences page and sources management page — not built
- Alembic initial migration — must be generated after first `docker compose up`
- Structured logging — currently basic Python logging
- Rate limiting on auth endpoints
- Feed sort: `?sort=relevance|date|importance` реализован; идеи для дальнейшего развития:
  - Семантический поиск (Qdrant) — см. `project_semantic_search.md`
  - Фильтр по языку (`?lang=ru|en`) в UI
  - Фильтр по источнику / теме через чипы
  - Улучшить topic-фильтр в relevance-режиме: исключать новости где нежелательный топик доминирует (сейчас фильтр по `has_key` слишком мягкий)
- Настройки пользователя (фронт + бот):
  - Тема оформления (светлая / тёмная / системная)
  - Выбор шрифта (размер или семейство)
  - Язык интерфейса (ru / en)

## Running locally

```bash
cp .env.example .env  # fill required vars
docker compose up --build
```

API docs: http://localhost:8000/api/docs

## First migration

```bash
docker compose exec backend alembic revision --autogenerate -m "init"
docker compose exec backend alembic upgrade head
```
