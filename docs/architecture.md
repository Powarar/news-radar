# News Radar — Architecture

News Radar — это персональный новостной агрегатор. Он парсит Telegram-каналы и сайты,
классифицирует новости по темам через AI, суммаризирует их, и показывает каждому
пользователю ленту, отсортированную по его интересам. Интересы накапливаются автоматически
через реакции (лайк/дизлайк).

**Стек:** FastAPI + PostgreSQL 16 + Celery + Redis + Groq (LLM) + React 18 + aiogram 3 + Docker

---

## Содержание

- [Архитектура](#архитектура)
- [Полный поток данных](#полный-поток-данных)
- [AI пайплайн](#ai-пайплайн)
- [Ранжирование ленты](#ранжирование-ленты)
- [Накопление предпочтений](#накопление-предпочтений)
- [Telegram-уведомления](#telegram-уведомления)
- [Авторизация](#авторизация)
- [Celery очередь](#celery-очередь)
- [Структура репозитория](#структура-репозитория)
- [Запуск](#запуск)

---

## Архитектура

```
                         nginx (:80)
                        /           \
                       /             \
              frontend (Vite :5173)   backend (FastAPI :8000)
               /  dev                 /    |        \
              /  или                  /     |         \
             /  nginx dist          /      |          \
            /                      db     redis      worker
           /                  (Postgres 16)  |      (Celery)
          /                                 |
     Telegram бот ────────────────────────  |
     (aiogram 3 polling,                   |
      вызывает backend API)                |
                                           |
     Telegram пользователи ──────────────  |
     (получают уведомления с кнопками)     |
                                           |
     Groq API (llama-3.1-8b-instant) ─────┘
     (классификация + суммаризация)
```

### Компоненты

| Компонент | Роль |
|---|---|
| **nginx** | Reverse proxy: раздаёт фронтенд (build), проксирует `/api` → backend |
| **backend (FastAPI)** | REST API — auth, лента, реакции, преференсы, управления источниками |
| **db (PostgreSQL 16)** | Все данные: пользователи, новости, источники, реакции, предпочтения |
| **redis** | Очередь Celery, кеш токенов (blacklist, oauth коды), rate limiting |
| **worker (Celery)** | Фоновые задачи: парсинг (каждые 15 мин), AI-обогащение, отправка уведомлений |
| **frontend (React + Vite)** | SPA с тремя вкладками сортировки, авторизацией, страницей настроек |
| **bot (aiogram 3)** | Telegram-бот: подписка, топ новостей, уведомления с инлайн-кнопками |

---

## Полный поток данных

```
Каждые 15 минут (Celery Beat)
         │
         ▼
  fetch_sources()
         │
         ├─► fetch_telegram_channel()   ──► парсит t.me/s/ через BeautifulSoup
         └─► fetch_website()            ──► RSS (feedparser) → HTML (BeautifulSoup)
                  │
                  ▼  сохраняет NewsItem
         process_news_ai(news.id)
                  │
                  ├─► classify(text)         ──► Groq → {topic: score}
                  │                               fallback: keyword regex
                  │
                  ├─► score_importance(topics)    ──► max(topic) × exp_decay (заглушка)
                  │
                  ├─► summarize(text)        ──► Groq → 1 предложение
                  │
                  └─► send_notifications()
                           │
                           ▼
                  send_single_notification(пользователь)
                           │
                           ▼
                  Telegram: [Текст] [👍 👎 ✖]

Пользователь реагирует (сайт или Telegram)
         │
         ▼
  POST /news/{id}/react
         │
         ├─► сохраняет/переключает реакцию в БД
         └─► update_topic_preferences.delay()
                  │
                  ▼
         Для каждой темы новости с score ≥ 0.3:
           weight += (0.1 если лайк, -0.1 если дизлайк) × confidence
           weight = clamp(0.0, 1.0)

Пользователь открывает ленту
         │
         ▼
  GET /news?sort=relevance&limit=20&offset=0
         │
         ▼
  relevance = Σ(user_weight × news_topic_score)
  decay = exp(-возраст_часы / 24)
  score = relevance × decay
         │
         ▼
  Ответ: { items, total, offset, limit }
```

---

## AI пайплайн

### Классификация (`services/ai/classifier.py`)

Groq (`llama-3.1-8b-instant`) получает текст новости и возвращает уверенность 0.0–1.0
по 9 темам:

```
politics, military, technology, health, science, business, sports, culture, environment
```

Если Groq недоступен или API-ключа нет — срабатывает **keyword fallback**: регулярные
выражения на русском и английском, сопоставленные с темами.

**Хранение:** JSON-строка в поле `news_items.topics`, например:
```json
{"technology": 0.9, "business": 0.3}
```

### Суммаризация (`services/ai/summarizer.py`)

Groq получает текст и возвращает одно предложение (≈15 слов) на языке оригинала.
Если ответ длиннее — обрезается до первого `.`.
Retry: до 4 попыток с экспоненциальной задержкой (0.5 → 1 → 2 → 4 сек).

### Importance (`services/ai/importance.py`)

**Сейчас заглушка:**

```python
def score_importance(topic_scores: dict[str, float]) -> float:
    return round(max(topic_scores.values()) * 0.6, 3)
```

Нужно заменить на формулу, учитывающую: вес источника, количество реакций, время суток
и другие факторы. (См. TODO.md → ML importance scoring)

---

## Ранжирование ленты

У ленты три режима сортировки, переключаемых через параметр `?sort=`.

### 1. «Новые» (`sort=date`)

Чистая хронология. `ORDER BY published_at DESC`. Единственный режим для неавторизованных.

### 2. «Важные» (`sort=importance`)

`ORDER BY importance_score DESC, date DESC`. Использует заглушку — все новости
получают примерно одинаковый балл. TODO.

### 3. «Для вас» (`sort=relevance`) — основной алгоритм

Только для авторизованных пользователей. Четыре шага:

**Шаг 1 — Заблокированные источники**

Если пользователь нажал ✖ на новости, источник попадает в `user_source_settings`
с `blacklisted = true`. Все новости этого источника исключаются подзапросом.

**Шаг 2 — Исключение тем «Не читаю»**

Если пользователь поставил теме `weight = 0.0`, новости где эта тема доминирует
(confidence > 0.5) скрываются. Если тема есть, но не доминирует — новость
показывается (другая любимая тема перевешивает).

**Шаг 3 — Релевантность**

Для каждой темы, где у пользователя `weight > 0`:
```
relevance = SUM(user_weight[topic] × news_topic_score[topic])
```

Это dot product вектора предпочтений пользователя и вектора тем новости.
Новости с `relevance ≤ 0.05` отфильтровываются.

**Шаг 4 — Decay сортировка**

Самый важный шаг. Вместо группировки по дням (которая хоронила старые
релевантные новости) используется **экспоненциальный decay**:

```
age_seconds = NOW() - published_at
decay = exp(-age_hours / 24)
score = relevance × decay
ORDER BY score DESC, date DESC
```

| Возраст | Множитель decay | Что значит |
|---|---|---|
| 0 часов | 1.0 | Полный вес |
| 24 часа | ~0.37 | Новость теряет 63% веса |
| 48 часов | ~0.14 | Едва заметна |
| 72 часа | ~0.05 | Практически не видна |

Статья с relevance = 0.9 через сутки (score ≈ 0.33) всё ещё может быть выше
свежей статьи с relevance = 0.1 (score = 0.1). Но через 2 дня — уже нет.

Константа `TAU = 24` настраивается в `NewsRepository`: чем меньше, тем быстрее
умирают старые новости.

---

## Накопление предпочтений

### Явные (через UI)

`PUT /api/v1/preferences` — пользователь вручную выставляет вес для каждой темы
от 0.0 («Не читаю») до 1.0. Полностью заменяет все предпочтения атомарно.

### Неявные (через реакции)

После каждого лайка/дизлайка воркер `update_topic_preferences` корректирует веса:

```python
delta = 0.1 if reaction == "like" else -0.1

for topic, confidence in news_topics.items():
    if confidence < 0.3:       # игнорируем слабые темы
        continue
    weight = current + delta * confidence
    weight = clamp(0.0, 1.0)  # не выходим за границы
```

Чем увереннее AI в теме новости, тем сильнее меняется вес.

**Пример:** Пользователь лайкнул новость с `{technology: 0.9, business: 0.3}`:
- technology: `0.5 + 0.1 × 0.9 = 0.59`
- business: `0.5 + 0.1 × 0.3 = 0.53`

Дизлайк той же новости:
- technology: `0.5 - 0.1 × 0.9 = 0.41`
- business: `0.5 - 0.1 × 0.3 = 0.47`

### Холодный старт

Новый пользователь без единой реакции получает хронологическую ленту.
Как только появляются реакции — включается персонализация.

---

## Telegram-уведомления

### Кто получает

- Пользователи с `telegram_id IS NOT NULL` и `notifications_enabled = true`
- Из них — те, у котя хотя бы одна тема пересекается с новостью (confidence > 0.2)
- Если у пользователя нет предпочтений → считается новым подписчиком, получает всё

### Что не отправляется

- Новости старше 2 часов (защита от флуда при перезапуске воркера после простоя)
- Новости без топиков (AI не смог классифицировать)
- Новости, где все предпочтения пользователя = 0.0

### Формат сообщения

- **Telegram-пост:** первые 160 символов как заголовок
- **Сайт:** оригинальный заголовок + суммаризация
- Внизу: темы с процентами, ссылка «Подробнее», инлайн-кнопки 👍 👎 ✖

### Очередь `notifications` (баг)

Celery `task_routes` отправляет задачи уведомлений в очередь `notifications`,
но воркер запущен только с очередями `default,parsing,ai`. Задачи не выполняются —
см. `AGENTS.md` → Gotchas.

---

## Авторизация

### Способы

| Способ | Описание |
|---|---|
| **Email + пароль** | Регистрация/логин, JWT access (24ч) + refresh (30д) |
| **Google OAuth** | OAuth 2.0 flow, PKCE |
| **Telegram Web App** | Mini App с initData, подпись через HMAC |

### Refresh token

Сейчас хранится в `localStorage` на фронте. TODO: перенести в httpOnly cookie
для защиты от XSS.

---

## Celery очередь

### Beat-задачи

| Задача | Расписание | Очередь |
|---|---|---|
| `fetch_sources` | Каждые 15 минут | `parsing` |

### Worker-задачи

| Задача | Когда | Очередь |
|---|---|---|
| `fetch_telegram_channel` | Из `fetch_sources` | `parsing` |
| `fetch_website` | Из `fetch_sources` | `parsing` |
| `process_news_ai` | После сохранения новости | `ai` |
| `reprocess_news_ai` | Ручной рестарт | `ai` |
| `update_topic_preferences` | После реакции | `preferences` 🚫 |
| `send_notifications` | После AI-обогащения | `notifications` 🚫 |
| `send_single_notification` | Из `send_notifications` | `notifications` 🚫 |

🚫 — эти очереди не подключены к воркеру, задачи не выполняются.

### Retry

| Задача | Есть retry? |
|---|---|
| `process_news_ai` | ✅ 3 попытки, exponential backoff |
| `send_single_notification` | ✅ 3 попытки |
| Остальные задачи парсинга | ❌ Нет |

---

## Структура репозитория

```
news-radar/
├── backend/
│   └── app/
│       ├── api/v1/routes/    # auth, news, sources, preferences, users, bot
│       ├── core/             # config, db (async), redis, security
│       ├── models/           # SQLAlchemy ORM (5 таблиц)
│       ├── repositories/     # DB queries (NewsRepository, SourcesRepository)
│       ├── services/
│       │   ├── ai/           # classifier, summarizer, importance
│       │   └── parser/       # telegram, web/rss
│       └── workers/          # Celery app + tasks + beat
├── frontend/
│   └── src/
│       ├── api/              # axios с интерцептором токена
│       ├── components/       # FeedPage, PreferencesPage, SourcesPage, NavBar
│       └── App.tsx           # useUser, useTelegramWebApp, маршруты
├── bot/
│   └── handlers/             # /start, /top, /subscribe, /unsubscribe
├── nginx/nginx.conf
├── docker-compose.yml
├── docker-compose.prod.yml
└── docs/
    ├── architecture.md       # этот файл
    ├── how_it_works.md       # заметки о фиксах и решениях
    ├── schema.md             # ER-диаграмма
    └── telegram-auth.md      # детально как работает Telegram OAuth
```

---

## Запуск

```bash
# dev
cp .env.example .env         # заполнить SECRET_KEY, GROQ_API_KEY и т.д.
docker compose up --build

# после первого запуска — создать таблицы
docker compose exec backend alembic revision --autogenerate -m "init"
docker compose exec backend alembic upgrade head

# prod
cp .env.example .env.prod
docker compose -f docker-compose.prod.yml up -d --build

# тесты (нужен запущенный Postgres)
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest

# линтер
ruff check .
```

### Сервисы

| URL | Сервис |
|---|---|
| http://localhost:5173 | Фронтенд (dev) |
| http://localhost:8000/api/docs | Swagger API |
| http://localhost:5555 | Flower (Celery UI) |

---

## Ключевые константы

| Константа | Где | Значение |
|---|---|---|
| `TAU = 24` | `repositories/news.py` | Decay в часах |
| `LIMIT` | Фронт + бэкенд | 20 новостей на страницу |
| `MAX_RETRIES = 3` | `workers/tasks.py` | Попыток AI пайплайна |
| `relevance_threshold = 0.05` | `repositories/news.py` | Минимальная релевантность |
| `topic_confidence_min = 0.3` | `workers/tasks.py` | Порог учёта темы в реакции |
| `topic_exclude_threshold = 0.5` | `repositories/news.py` | Порог доминирования исключённой темы |
| `notification_age_limit = 2h` | `workers/tasks.py` | Не отправлять старые новости |
