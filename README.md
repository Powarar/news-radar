# News Radar

News aggregator with AI personalization. Parses Telegram channels and websites, classifies articles by topic, summarizes them, and learns what each user wants to read.

Pet project: FastAPI backend, React frontend, Telegram bot, all in Docker.

## What it does

- Parses Telegram channels and websites (RSS first, falls back to HTML scraping)
- Classifies articles by topic using HuggingFace zero-shot classification
- Summarizes in the original language — 45+ languages supported
- Learns from user reactions: like/dislike shifts topic weights over time
- Works as a web app and Telegram bot
- Auth via Google OAuth, Telegram, and email/password

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + SQLAlchemy 2 + Alembic |
| Database | PostgreSQL 16 |
| Task queue | Celery + Redis |
| AI | HuggingFace Inference API |
| Parser | aiohttp + BeautifulSoup + feedparser |
| Frontend | React 18 + TypeScript + Vite (PWA) |
| Bot | aiogram 3 |
| Proxy | Nginx |
| Monitoring | Prometheus + Grafana + Flower |
| Infrastructure | Docker Compose |

## Structure

```
news-radar/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/    # auth, news, sources, preferences, users
│   │   ├── core/             # config, db, security, redis, rate_limit
│   │   ├── models/           # ORM models
│   │   ├── repositories/     # DB queries
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/
│   │   │   ├── ai/           # classifier, summarizer, importance scorer
│   │   │   └── parser/       # telegram, web/RSS
│   │   └── workers/          # Celery tasks + beat schedule
├── frontend/src/
│   ├── api/                  # axios client with refresh token logic
│   ├── components/           # FeedPage, LoginPage, ProfilePage, PreferencesPage, SourcesPage
│   └── types/
├── bot/handlers/             # /start, /top, settings
├── nginx/nginx.conf
├── prometheus/prometheus.yml
├── docker-compose.yml        # dev
└── docker-compose.prod.yml   # prod
```

## Running locally

Only Docker required.

```bash
git clone https://github.com/Powarar/news-radar.git
cd news-radar
cp .env.example .env
docker compose up --build
```

First run — create the tables:

```bash
docker compose exec backend alembic revision --autogenerate -m "init"
docker compose exec backend alembic upgrade head
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/api/docs |
| Flower | http://localhost:5555 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

## Environment variables

```bash
SECRET_KEY=           # openssl rand -hex 32
POSTGRES_PASSWORD=
TELEGRAM_BOT_TOKEN=   # from @BotFather
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
HUGGINGFACE_API_TOKEN=
```

## API

Auth endpoints `/login` and `/register` are rate-limited to **5 requests/minute per IP**.

| Method | Endpoint | |
|---|---|---|
| POST | /api/v1/auth/register | ✅ |
| POST | /api/v1/auth/login | ✅ |
| POST | /api/v1/auth/refresh | ✅ |
| POST | /api/v1/auth/logout | ✅ |
| GET | /api/v1/auth/google | ✅ |
| POST | /api/v1/auth/telegram | ✅ |
| GET | /api/v1/news | ✅ |
| GET | /api/v1/news/{id} | ✅ |
| POST | /api/v1/news/{id}/react | ✅ |
| GET | /api/v1/users/me | ✅ |
| PATCH | /api/v1/users/me | ✅ |
| GET | /api/v1/sources | ✅ |
| POST | /api/v1/sources | ✅ |
| PATCH | /api/v1/sources/{id}/toggle | ✅ |
| PATCH | /api/v1/sources/{id}/blacklist | ✅ |
| GET | /api/v1/preferences | ✅ |
| PUT | /api/v1/preferences | ✅ |

## Background tasks

Three Celery queues: `parsing`, `ai`, `default`, `notifications`, `preferences`.

- `fetch_sources` — runs every 15 min via beat, dispatches tasks per source
- `fetch_telegram_channel` / `fetch_website` — fetch new items, deduplicate by URL
- `process_news_ai` — parallel classify + summarize via asyncio.gather
- `update_topic_preferences` — adjusts user topic weights after each reaction
- `send_notifications` — pushes matched news to Telegram users based on their topic preferences

## Production

```bash
cp .env.example .env.prod
docker compose -f docker-compose.prod.yml up -d --build
```

Prometheus and Grafana are internal only — not exposed publicly in prod.
