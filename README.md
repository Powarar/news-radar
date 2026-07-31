# News Radar

Персональный новостной агрегатор с AI-классификацией, русскоязычными саммари,
адаптивной лентой и Telegram-интеграцией.

Проект собирает новости из Telegram-каналов, RSS и сайтов, обрабатывает их в
фоновых задачах, определяет темы, формирует краткое саммари и ранжирует выдачу
по интересам конкретного пользователя.

## Что реализовано

- регистрация и вход по email/password;
- JWT access/refresh tokens, выход с отзывом access token через Redis;
- Google OAuth и автоматическая авторизация Telegram Mini App;
- просмотр и добавление источников, персональные toggle/blacklist-настройки;
- парсинг Telegram-каналов, RSS и HTML-страниц;
- дедупликация новостей по URL;
- AI-классификация по девяти темам;
- краткое саммари только на русском языке;
- персональная лента с учётом интересов и свежести;
- режимы «Для вас», «Важные» и «Новые»;
- явная настройка интересов и их адаптация после like/dislike;
- блокировка источника из карточки новости;
- Telegram-уведомления по выбранным темам;
- фоновые задачи, очереди, периодический запуск и повторные попытки;
- Swagger/ReDoc, healthcheck и Prometheus-метрики;
- Docker Compose для разработки и production;
- CI: Ruff, pytest с PostgreSQL и автоматический deploy из `main`.

## Архитектура

```mermaid
flowchart LR
    U["Пользователь"] --> N["Nginx"]
    N --> F["React / Vite"]
    N --> A["FastAPI"]
    B["Telegram Bot"] --> A
    A --> P[("PostgreSQL 16")]
    A --> R[("Redis 7")]
    C["Celery Beat"] --> W["Celery Worker"]
    W --> R
    W --> P
    W --> S["Telegram / RSS / сайты"]
    W --> G["Groq API"]
    W --> B
```

Путь одной новости:

1. Celery Beat каждые 15 минут запускает `fetch_sources`.
2. Задача распределяет источники в очередь `parsing`.
3. Worker парсит источник, проверяет URL и сохраняет только новые записи.
4. `process_news_ai` классифицирует новость, создаёт русское саммари и
   рассчитывает эвристическую важность.
5. Новость становится доступна API и при совпадении тем отправляется
   подписанным пользователям Telegram.
6. Like/dislike асинхронно корректирует веса тем пользователя.

## Почему архитектура устроена так

### FastAPI работает асинхронно, Celery — синхронно

HTTP API обслуживает множество коротких I/O-запросов, поэтому использует
`AsyncSession` и `asyncpg`. Celery выполняет изолированные фоновые задачи в
отдельных процессах; для них обычный синхронный SQLAlchemy session проще и
предсказуемее. Поэтому в проекте намеренно существуют два подключения:
`database_url` и `database_url_sync`.

### Парсинг и AI вынесены из HTTP-запросов

Загрузка внешнего сайта или ответ AI-провайдера могут занимать секунды и
завершаться ошибкой. Если выполнять их в FastAPI, пользовательский запрос будет
висеть и занимать worker. Celery позволяет использовать отдельные очереди,
retry/backoff и независимо масштабировать тяжёлые операции.

### Redis выполняет несколько ролей

Redis используется как broker/result backend Celery, хранилище отозванных JWT и
основа sliding-window rate limiter. Это уменьшает число инфраструктурных
компонентов для проекта, сохраняя атомарность операций.

### PostgreSQL вместо SQLite

Персональная выдача использует JSONB-операторы и вычисляемое SQL-ранжирование.
Тесты также запускаются на PostgreSQL, чтобы тестовая и production-семантика не
расходились.

## Персональная лента

Есть три режима:

- `relevance` — «Для вас»;
- `importance` — «Важные»;
- `date` — «Новые».

Для авторизованного пользователя режим «Для вас»:

1. исключает заблокированные источники;
2. исключает новости с темами, которым пользователь присвоил вес `0`;
3. отсекает новости старше трёх дней;
4. убирает записи с практически нулевой релевантностью;
5. рассчитывает нормализованное тематическое совпадение:

   ```text
   relevance = Σ(user_topic_weight × news_topic_score) / Σ(user_topic_weight)
   ```

6. добавляет плавный коэффициент свежести внутри трёхдневного окна:

   ```text
   personalized_score = relevance × 0.90 + freshness × 0.10
   ```

Так предпочтения остаются главным сигналом, а из двух сопоставимых новостей
выше оказывается более свежая. Если предпочтения ещё не заданы, применяется
сортировка по дате, но трёхдневное ограничение сохраняется.

Первый запрос фронтенда ждёт завершения `/users/me`. Авторизованный пользователь
сразу получает `sort=relevance`; гостевой запрос отправляется с `sort=date`.
Это предотвращает показ общей ленты под активной вкладкой «Для вас».

## AI-пайплайн

Один запрос к Groq выполняет две операции:

- классифицирует новость по темам `politics`, `military`, `technology`,
  `health`, `science`, `business`, `sports`, `culture`, `environment`;
- формирует нейтральное саммари одним предложением только на русском языке,
  независимо от языка источника.

Сейчас используется `llama-3.1-8b-instant`. При недоступном Groq классификация
переходит на локальный keyword fallback; саммари пропускается, а задача может
быть переотправлена на обработку позднее.

`importance_score` — не обученная ML-модель, а объяснимая эвристика. Она
сравнивает topic score новости с последними 200 классифицированными записями и
использует максимальный внутритематический percentile. Это рабочий baseline;
следующий шаг — обучение на размеченных данных и пользовательских реакциях.

## Стек

| Слой | Технологии |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic |
| ORM и миграции | SQLAlchemy 2, Alembic |
| База данных | PostgreSQL 16, JSONB |
| Фоновые задачи | Celery, Celery Beat, Redis |
| AI | Groq API, keyword fallback |
| Парсинг | httpx, BeautifulSoup, feedparser |
| Frontend | React 18, TypeScript, Vite |
| Telegram | aiogram 3, Telegram Mini App |
| Инфраструктура | Docker Compose, Nginx |
| Наблюдаемость | Prometheus, Grafana, Flower |
| CI/CD | GitHub Actions |

## Структура репозитория

```text
news-radar/
├── backend/
│   ├── alembic/                 # миграции
│   ├── app/
│   │   ├── api/v1/routes/       # HTTP API
│   │   ├── core/                # config, DB, Redis, security
│   │   ├── models/              # SQLAlchemy ORM
│   │   ├── repositories/        # запросы к данным
│   │   ├── schemas/             # Pydantic DTO
│   │   ├── services/ai/         # AI и importance scoring
│   │   ├── services/parser/     # Telegram/RSS/web parsing
│   │   └── workers/             # Celery tasks и routing
│   └── tests/
├── frontend/src/
│   ├── api/                     # Axios и refresh flow
│   └── components/              # настройки тем и источников
├── bot/handlers/                # команды и callback-кнопки
├── nginx/
├── prometheus/
├── docker-compose.yml
└── docker-compose.prod.yml
```

## Быстрый запуск через Docker

Потребуются Docker Engine и Docker Compose.

```bash
git clone https://github.com/Powarar/news-radar.git
cd news-radar
cp .env.example .env
```

Для локальной демонстрации замените `SECRET_KEY`:

```bash
openssl rand -hex 32
```

Вставьте результат в `.env`. Если хотите запускать Telegram-бот вместе со всем
стеком, также заполните `TELEGRAM_BOT_TOKEN`. Затем запустите сервисы:

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose ps
```

Без Telegram-токена можно поднять только web-часть и инфраструктуру:

```bash
docker compose up --build -d \
  db redis backend worker beat frontend flower prometheus grafana
docker compose exec backend alembic upgrade head
```

Создавать новую migration-командой `alembic revision --autogenerate` при первом
запуске не нужно: миграции уже находятся в репозитории.

После запуска:

| Сервис | Адрес |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/api/docs |
| ReDoc | http://localhost:8000/api/redoc |
| Healthcheck | http://localhost:8000/api/health |
| Metrics | http://localhost:8000/api/metrics |
| Flower | http://localhost:5555 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

Логи основных компонентов:

```bash
docker compose logs -f backend worker beat frontend
```

Остановка:

```bash
docker compose down
```

Удаление локальных данных PostgreSQL и Redis:

```bash
docker compose down -v
```

Последняя команда необратимо удаляет development volumes.

## Переменные окружения

| Переменная | Обязательна | Назначение |
|---|---:|---|
| `SECRET_KEY` | да | подпись JWT и server-side session |
| `OAUTH_CODE_TTL` | да | TTL одноразового OAuth-кода |
| `POSTGRES_*` | да | параметры PostgreSQL |
| `REDIS_URL` | да | Celery, blacklist JWT, rate limiting |
| `GROQ_API_KEY` | нет | AI-классификация и русское саммари |
| `TELEGRAM_BOT_TOKEN` | для бота | токен от BotFather |
| `TELEGRAM_API_ID/HASH` | для TG parsing | доступ Telethon |
| `GOOGLE_CLIENT_ID/SECRET` | для Google OAuth | OAuth credentials |
| `GOOGLE_REDIRECT_URI` | для Google OAuth | callback URL backend |
| `BACKEND_URL` | для бота | внутренний URL FastAPI |
| `FRONTEND_URL` | для Mini App | публичный URL frontend |
| `VITE_API_URL` | frontend | URL API во время сборки |
| `VITE_TG_BOT_USERNAME` | Mini App | username Telegram-бота |

Без `GROQ_API_KEY` проект остаётся работоспособным: новости классифицируются по
ключевым словам, но AI-саммари не создаются.

## Локальная разработка без Docker для приложения

PostgreSQL и Redis всё равно должны быть доступны.

Backend:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
set -a
source .env
set +a
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

Worker и scheduler запускаются в отдельных терминалах из `backend/`:

```bash
celery -A app.workers.celery_app worker \
  --loglevel=info \
  -Q default,parsing,ai,notifications,preferences
```

```bash
celery -A app.workers.celery_app beat --loglevel=info
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Миграции

Применить существующие миграции:

```bash
docker compose exec backend alembic upgrade head
```

После изменения ORM-моделей:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

Проверить текущую ревизию:

```bash
docker compose exec backend alembic current
docker compose exec backend alembic history
```

Новая модель должна быть импортирована в `backend/alembic/env.py`, иначе
autogenerate её не увидит.

## API

Все пользовательские маршруты находятся под `/api/v1/`.

| Метод | Маршрут | Авторизация | Назначение |
|---|---|---:|---|
| `POST` | `/auth/register` | нет | регистрация |
| `POST` | `/auth/login` | нет | вход |
| `POST` | `/auth/refresh` | refresh token | обновление токенов |
| `POST` | `/auth/logout` | bearer | отзыв access token |
| `GET` | `/auth/google/login` | нет | начало Google OAuth |
| `GET` | `/auth/google/callback` | нет | OAuth callback |
| `POST` | `/auth/telegram/webapp` | Telegram initData | вход Mini App |
| `GET` | `/users/me` | bearer | текущий пользователь |
| `PATCH` | `/users/me` | bearer | изменение профиля |
| `GET` | `/news/?sort=...` | опционально | лента |
| `GET` | `/news/{id}` | нет | одна новость |
| `POST` | `/news/{id}/react` | bearer | like/dislike/blacklist |
| `GET` | `/preferences/` | bearer | веса тем |
| `PUT` | `/preferences/` | bearer | обновление весов |
| `GET` | `/sources/` | опционально | список источников |
| `POST` | `/sources/` | admin bearer | новый глобальный источник |
| `PATCH` | `/sources/{id}/toggle` | bearer | включить/выключить |
| `PATCH` | `/sources/{id}/blacklist` | bearer | скрыть источник |

Полная и всегда актуальная схема доступна в Swagger: `/api/docs`.

### Администратор

Добавлять глобальные источники может только пользователь с `users.is_admin =
true`. Обычные пользователи по-прежнему могут включать, отключать и скрывать
источники только для своей ленты.

После применения миграций назначьте администратора по email:

```bash
docker compose -f docker-compose.prod.yml exec -T db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c \
  "UPDATE users SET is_admin = TRUE WHERE email = '\''pshsafonov@gmail.com'\'';"'
```

Проверить результат:

```bash
docker compose -f docker-compose.prod.yml exec -T db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT id, email, username, is_admin, plan FROM users WHERE email = '\''pshsafonov@gmail.com'\'';"'
```

## Очереди и фоновые задачи

| Очередь | Задачи |
|---|---|
| `parsing` | `fetch_sources`, `fetch_telegram_channel`, `fetch_website` |
| `ai` | `process_news_ai` |
| `preferences` | `update_topic_preferences` |
| `notifications` | `send_notifications`, `send_single_notification` |
| `default` | служебные/ручные задачи |

Worker обязан слушать все перечисленные очереди. Это уже настроено в обоих
Compose-файлах.

Повторно обработать новости без саммари:

```bash
docker compose exec worker \
  celery -A app.workers.celery_app call \
  app.workers.tasks.reprocess_news_ai
```

Принудительно запустить сбор источников:

```bash
docker compose exec worker \
  celery -A app.workers.celery_app call \
  app.workers.tasks.fetch_sources
```

## Telegram

Бот поддерживает:

- `/start` — открыть Mini App и автоматически войти;
- `/top` — показать пять последних новостей;
- `/subscribe` — включить тематические уведомления;
- `/unsubscribe` — отключить уведомления;
- `/settings` — показать доступные настройки.

Для production Mini App требует публичный HTTPS URL в `FRONTEND_URL`. URL
приложения и команды задаются через BotFather.

## Тесты и качество

Backend-тесты используют настоящий PostgreSQL, а не SQLite:

```bash
createdb newsradar_test
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/newsradar_test
cd backend
pytest
```

Или запустите PostgreSQL через Compose и выполняйте тесты с хоста.

Lint:

```bash
cd backend
ruff check .
```

Frontend:

```bash
cd frontend
npm run build
```

CI при push в `main` поднимает PostgreSQL, выполняет Ruff и pytest, после чего
production job подключается к серверу по SSH, обновляет контейнеры и применяет
Alembic migrations.

## Production

1. Создайте `.env.prod` непосредственно на сервере и не добавляйте его в Git.
2. Укажите production URL для frontend, Google OAuth и Telegram Mini App.
3. Запустите:

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head
   ```

4. Проверьте:

   ```bash
   docker compose -f docker-compose.prod.yml ps
   curl -f http://localhost/api/health
   ```

В production Nginx обслуживает frontend, проксирует `/api/` в FastAPI и
ограничивает API до 30 запросов в минуту с burst 20. PostgreSQL и Flower
привязаны только к loopback-интерфейсу.

Перед публичным запуском необходимо настроить TLS reverse proxy или Certbot,
регулярный `pg_dump`, ротацию секретов и внешний мониторинг.

## Ограничения и дальнейшее развитие

Проект является законченным MVP, но не заявляет, что решил все возможные задачи
новостной платформы. Осознанно оставлены следующие направления:

- обучаемая модель важности вместо percentile baseline;
- semantic search и RAG;
- кластеризация дублей одного события из разных источников;
- cursor pagination для большой персональной ленты;
- refresh token в httpOnly cookie вместо `localStorage`;
- лимиты количества Telegram-уведомлений;
- резервное копирование, TLS и полноценный secrets manager.

Подробный roadmap находится в [`TODO.md`](TODO.md). Эти пункты не блокируют
основные сценарии: сбор новостей, AI-обработку, персональную выдачу, управление
источниками и Telegram-уведомления.

## Как презентовать проект на собеседовании

Короткая демонстрация занимает пять минут:

1. Открыть Swagger и показать границы API.
2. Добавить источник через web-интерфейс.
3. Запустить `fetch_sources` и показать движение задачи во Flower.
4. Открыть обработанную новость с темами и русским саммари.
5. Настроить интересы и сравнить «Для вас» с «Новыми».
6. Поставить like и объяснить асинхронное изменение весов.
7. Показать healthcheck, metrics и pipeline GitHub Actions.

Важные инженерные вопросы, на которые стоит уметь ответить:

- почему внешний парсинг и AI нельзя выполнять внутри HTTP-request;
- зачем API использует async SQLAlchemy, а Celery worker — sync;
- как обеспечивается дедупликация и что произойдёт при повторном запуске задачи;
- почему тематический score весит 90%, а freshness только 10%;
- почему интеграционные тесты используют PostgreSQL, а не SQLite;
- как система ведёт себя при недоступном Groq, Redis или отдельном источнике;
- какие гарантии нужны для production: идемпотентность, backup, TLS,
  observability и безопасное хранение refresh token.

Проект демонстрирует архитектурные навыки уровня выше обычного CRUD. Грейд
разработчика определяется не количеством технологий в README, а способностью
объяснить эти решения, их ограничения и альтернативы.
