# AGENTS.md — News Radar

## Quick commands

```bash
cp .env.example .env    # then fill required vars (SECRET_KEY, tokens)
docker compose up --build

# First run only — create DB tables:
docker compose exec backend alembic revision --autogenerate -m "init"
docker compose exec backend alembic upgrade head

# Backend tests (needs a running Postgres):
cd backend && pip install -r requirements.txt -r requirements-dev.txt && pytest

# Lint (CI runs this; no config in repo, ruff auto-detects):
cd backend && pip install ruff && ruff check .
```

## Architecture

```
nginx (:80) → frontend (Vite dev :5173, or prod nginx serving dist)
            → backend (FastAPI :8000) → db (Postgres 16), redis
worker (Celery: parsing, ai, default queues) + beat (every 15 min)
bot (aiogram 3 polling, calls backend API)
```

- All routes under `/api/v1/`. Swagger at `/api/docs`.
- Auth: JWT (access 24h + refresh 30d) + Google OAuth + Telegram.
- ORM: async SQLAlchemy 2 for FastAPI. **Sync SQLAlchemy for Celery tasks** — two separate engine setups (`database_url` vs `database_url_sync`).
- AI: HuggingFace Inference API (`facebook/bart-large-mnli` classifier, `csebuetnlp/mT5_multilingual_XLSum` summarizer).
- Frontend: React 18 + TypeScript + Vite. Dev server proxies `/api` → `http://backend:8000`. In prod, `VITE_API_URL` points to the real API URL. The build script is `tsc && vite build` — `tsc` runs as a type-check pass only (`noEmit: true`).

## Gotchas

- **Celery queue mismatch:** `task_routes` sends `update_topic_preferences` to queue `preferences` and `send_notifications` to `notifications`, but the worker only listens to `default,parsing,ai`. Those tasks will never execute until the worker command is updated.
- **Volume mounts override the image:** `docker-compose.yml` mounts `./backend:/app` (and `./frontend/src:/app/src`). Adding a pip/npm dependency requires `docker compose up --build`, not just a restart.
- **Frontend lint is broken:** `eslint` is not installed and no config exists. The `lint` script in `package.json` will fail.
- **Bot `news.py` bug:** `httpx.AsyncClient` is used but not imported.
- **Tests need real Postgres:** Not SQLite. The conftest creates/drops a database via the `TEST_DATABASE_URL` env var (defaults to `localhost:5432/newsradar_test`).
- **`Settings()` is a module-level singleton** — imported at app startup from `app/core/config.py`. A missing required env var crashes the import, not a lazy error.
- **Redis connection also module-level** (`app/core/redis.py`). No lazy init.
- **Migrations detect models via explicit imports** in `alembic/env.py`. Adding a new model requires adding its import there.
- **Frontend actively unregisters service workers** in `main.tsx` — PWA is disabled in dev.
- **`.dockerignore` does not exist** in backend, frontend, or bot.

## Known stubs

- `app/services/ai/importance.py` — returns `max(topic_scores) * 0.6`
- `app/api/v1/routes/preferences.py` — all endpoints are `pass`
- `app/api/v1/routes/sources.py` — all endpoints are `pass`
- Bot `/settings` and `/sources` handlers — reply "coming soon"
- `send_notifications` Celery task — not implemented
- Frontend preferences page and sources management page — not built
- Rate limiting on auth endpoints — not done

## References

- `CLAUDE.md` — project overview and conventions (same info, more prose)
- `TODO.md` — detailed roadmap with status per item
- `README.md` — API table, service URLs, env vars
- `backend/pytest.ini` — test config (`asyncio_mode = auto`)
- `backend/alembic/env.py` — migration setup (async, explicit model imports)
- `.github/workflows/ci.yml` — lint → test → deploy pipeline (main branch only)
