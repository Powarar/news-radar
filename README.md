# News Radar

Global news aggregator with AI-powered personalization. Parses Telegram channels and websites, classifies content by topic, scores importance, and delivers relevant news to users via web app and Telegram bot.

## Features

- Parses Telegram channels (Telethon) and websites (RSS + HTML scraping)
- Topic classification via HuggingFace zero-shot (facebook/bart-large-mnli)
- Multilingual summarization (csebuetnlp/mT5_multilingual_XLSum, 45+ languages)
- Importance scoring per news item
- Per-user topic preferences with weights
- Enable/disable/blacklist individual sources
- Like/dislike/blacklist reactions on news
- Language and country filters
- Google OAuth + email/password auth
- Telegram bot with same functionality as web app
- PWA (installable on mobile)
- Free and Pro subscription plans

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16 |
| Queue | Celery + Redis |
| AI | HuggingFace Inference API |
| TG Parser | Telethon |
| Web Parser | httpx + BeautifulSoup + feedparser |
| Frontend | React 18, TypeScript, Vite, PWA |
| Bot | aiogram 3 |
| Proxy | Nginx |
| Deploy | Docker Compose |

## Project Structure

```
news-radar/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/    # auth, news, sources, preferences, users
│   │   ├── core/             # config, database, security
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/
│   │   │   ├── ai/           # classifier, summarizer, importance scorer
│   │   │   └── parser/       # telegram, web/RSS
│   │   ├── workers/          # Celery tasks and beat schedule
│   │   └── main.py
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/              # typed axios client
│   │   ├── components/       # ui, news, settings
│   │   ├── pages/            # Feed, Top, Sources, Preferences, Profile
│   │   ├── styles/           # global CSS with design tokens
│   │   └── types/            # TypeScript interfaces
│   ├── Dockerfile
│   └── vite.config.ts
├── bot/
│   ├── handlers/             # news, settings
│   └── main.py
├── nginx/nginx.conf
├── docker-compose.yml        # development
└── docker-compose.prod.yml   # production
```

## Getting Started

### Requirements

- Docker 24+
- Docker Compose v2

That is all you need. Everything else runs inside containers.

### Setup

```bash
git clone https://github.com/yourname/news-radar.git
cd news-radar

cp .env.example .env
# fill in .env (see section below)

docker compose up --build
```

Services will be available at:

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/api/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
# Required
SECRET_KEY=           # any random string, e.g.: openssl rand -hex 32
POSTGRES_PASSWORD=    # any password

# For Telegram parsing
TELEGRAM_API_ID=      # get at https://my.telegram.org
TELEGRAM_API_HASH=    # get at https://my.telegram.org

# For Telegram bot
TELEGRAM_BOT_TOKEN=   # get from @BotFather

# For Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# For AI features
HUGGINGFACE_API_TOKEN=  # get at https://huggingface.co/settings/tokens
```

### Database Migrations

```bash
# Create a new migration after changing models
docker compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec backend alembic upgrade head
```

## API Reference

Full interactive docs available at `/api/docs` (Swagger UI) when running locally.

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/v1/auth/register | Register with email/password |
| POST | /api/v1/auth/login | Login, get JWT |
| POST | /api/v1/auth/refresh | Refresh access token |
| GET | /api/v1/auth/google | Google OAuth redirect |
| GET | /api/v1/news | Personalized feed |
| GET | /api/v1/news/top | Top news by importance score |
| GET | /api/v1/news/{id} | Single news item |
| POST | /api/v1/news/{id}/react | Like / dislike / blacklist |
| GET | /api/v1/sources | All sources with user settings |
| PATCH | /api/v1/sources/{id}/toggle | Enable/disable source |
| PATCH | /api/v1/sources/{id}/blacklist | Blacklist source |
| GET | /api/v1/preferences | User topic preferences |
| PUT | /api/v1/preferences | Update preferences |
| GET | /api/v1/users/me | Current user profile |
| PATCH | /api/v1/users/me | Update profile |

## Deployment on Your Own Server

See `docker-compose.prod.yml` and `nginx/nginx.conf`.

```bash
# On your server
git clone ...
cp .env.example .env.prod
# fill in .env.prod

docker compose -f docker-compose.prod.yml up -d --build
```

For HTTPS, uncomment the SSL server block in `nginx/nginx.conf` and point to your certificates (e.g. from Let's Encrypt via certbot).
