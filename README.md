# News Radar

Personal news aggregator with AI-driven feed ranking. Parses Telegram channels and websites, classifies articles by topic, summarizes them, and adapts to what each user actually reads.

Pet project — FastAPI backend, React frontend, Telegram bot, Docker.

## How it works

Parsing runs every 15 minutes via Celery beat. Each article goes through classification and summarization (Groq, llama-3.1-8b-instant). Users get a feed sorted according to their preferences, which update automatically as they like and dislike articles.

### Feed ranking

The feed has three modes: **For you**, **Important**, **New**.

**For you** applies the following logic in order:

1. Remove articles from blacklisted sources
2. Remove articles where a topic the user set to "not reading" scores above 0.5 — even if another liked topic is also present in the article
3. Keep articles where `relevance = sum(user_topic_weight * article_topic_score) > 0.05`
4. Sort by day bucket, then time, then relevance descending

Topic weights live in `user_topic_preferences` (0.0-1.0). They are set explicitly in the preferences UI and adjusted automatically after each like/dislike reaction.

**Important** sorts by `importance_score` regardless of preferences. **New** is pure chronological order.

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + SQLAlchemy 2 + Alembic |
| Database | PostgreSQL 16 |
| Task queue | Celery + Redis |
| AI | Groq API (llama-3.1-8b-instant), keyword fallback |
| Parser | httpx + BeautifulSoup + feedparser |
| Frontend | React 18 + TypeScript + Vite (PWA) |
| Bot | aiogram 3 |
| Proxy | Nginx |
| Infrastructure | Docker Compose |

## Structure

```
news-radar/
├── backend/app/
│   ├── api/v1/routes/     # auth, news, sources, preferences, users, bot
│   ├── core/              # config, db, security
│   ├── models/            # SQLAlchemy ORM
│   ├── repositories/      # DB queries
│   ├── services/
│   │   ├── ai/            # classifier, summarizer, importance scorer
│   │   └── parser/        # telegram, web/RSS
│   └── workers/           # Celery tasks + beat schedule
├── frontend/src/
│   ├── api/               # axios client with token refresh
│   └── components/        # NavBar, PreferencesPage, SourcesPage
├── bot/handlers/          # /start, /top, /subscribe, /unsubscribe
├── nginx/nginx.conf
├── docker-compose.yml        # dev
└── docker-compose.prod.yml   # prod
```

## Running locally

Requires Docker.

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

## Environment variables

```env
SECRET_KEY=              # openssl rand -hex 32
POSTGRES_PASSWORD=
GROQ_API_KEY=
TELEGRAM_BOT_TOKEN=      # from @BotFather
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

## API

| Method | Endpoint | Status |
|---|---|---|
| POST | /api/v1/auth/register | done |
| POST | /api/v1/auth/login | done |
| POST | /api/v1/auth/refresh | done |
| POST | /api/v1/auth/logout | done |
| GET | /api/v1/auth/google | done |
| POST | /api/v1/auth/telegram | done |
| GET | /api/v1/news?sort=relevance\|importance\|date | done |
| GET | /api/v1/news/{id} | done |
| POST | /api/v1/news/{id}/react | done |
| GET | /api/v1/users/me | done |
| PATCH | /api/v1/users/me | done |
| GET | /api/v1/preferences | done |
| PUT | /api/v1/preferences | done |
| GET | /api/v1/sources | stub |
| POST | /api/v1/sources | stub |
| PATCH | /api/v1/sources/{id}/toggle | stub |

## Background tasks

Celery queues: `parsing`, `ai`, `notifications`, `preferences`.

- `fetch_sources` — every 15 min, dispatches one task per active source
- `fetch_telegram_channel` / `fetch_website` — fetch and deduplicate by URL
- `process_news_ai` — classify + summarize, then triggers `send_notifications`
- `update_topic_preferences` — adjusts topic weights after like/dislike
- `send_notifications` — sends matched articles to Telegram subscribers; users with no preferences yet receive everything

## Telegram bot

`/start` — opens the web app via Web App button  
`/top` — shows 5 latest articles with like/dislike/blacklist buttons  
`/subscribe` / `/unsubscribe` — enable or disable push notifications

## Production

```bash
cp .env.example .env.prod
docker compose -f docker-compose.prod.yml up -d --build
```
