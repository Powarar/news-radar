# TODO — News Radar

## Семантический поиск

Юзер пишет "что происходит с ИИ в Китае" → находит релевантные новости даже без этих слов. Векторный поиск по embeddings.

### Шаг 1 — Инфраструктура
- [ ] Добавить `qdrant` в `docker-compose.yml` (image: qdrant/qdrant, port 6333, volume qdrant_data)
- [ ] Добавить `QDRANT_URL=http://qdrant:6333` в `.env`

### Шаг 2 — Зависимости
- [ ] `sentence-transformers==3.0.1` и `qdrant-client==1.9.1` в `requirements.txt`
- [ ] В `Dockerfile` закешировать модель при билде: `RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"`

### Шаг 3 — Сервис эмбеддингов
- [ ] Создать `app/services/ai/embeddings.py` — `encode(text) -> list[float]`, модель через `@lru_cache(maxsize=1)`

### Шаг 4 — Qdrant коллекция
- [ ] Создать `app/core/qdrant.py` — клиент + `init_collection()` (cosine, 384d)
- [ ] Вызвать `init_collection()` в lifespan FastAPI

### Шаг 5 — Celery таска индексации
- [ ] Добавить `index_news(news_id, title, content, url)` в очередь `ai`
- [ ] Вызывать `index_news.delay(...)` после сохранения новости (рядом с `process_news_ai`)

### Шаг 6 — Эндпоинт поиска
- [ ] Создать `app/api/v1/routes/search.py` — `GET /search?q=...` → encode → qdrant.search(score_threshold=0.4) → get_by_ids
- [ ] Подключить роутер в `app/api/v1/__init__.py`

### Шаг 7 — Реиндексация
- [ ] Написать `scripts/reindex_news.py` — очередь Celery для всех существующих новостей

### Шаг 8 — Деплой
- [ ] Добавить qdrant в `docker-compose.prod.yml` (без expose порта наружу)
- [ ] Добавить `qdrant_data` в volumes

### После поиска
- [ ] RAG: Qdrant топ-5 → Groq генерирует ответ (+20 строк)
- [ ] Streaming SSE от Groq
- [ ] Redis кеш для одинаковых запросов
- [ ] Like/dislike на результаты → evaluation метрики

---

## AI / Контент

- [ ] Найти модель суммаризации которая не обрывает текст на полуслове (сейчас Groq, но может обрывать)
- [ ] Генерация заголовка если у новости нет title
- [ ] Добавить больше источников — RSS и Telegram каналы на ru/en

---

## DevOps и деплой

- [ ] ~~GitHub Actions~~ ✅ есть — lint + test + deploy на main
- [ ] ~~Healthcheck~~ ✅ уже есть — endpoint + docker-compose
- [ ] ~~Flower~~ ✅ есть — localhost:5555
- [ ] SSL в nginx — Let's Encrypt / Certbot
- [ ] Бэкапы PostgreSQL — pg_dump по крону
- [ ] Multi-stage Dockerfile — уменьшить размер образа бэкенда

---

## Качество кода

- [ ] ~~Тесты~~ ✅ есть — pytest + httpx для auth endpoints (CI проверяет)
- [ ] Celery retry — `autoretry_for=(Exception,), retry_backoff=True` на задачах **парсинга** (сейчас только на `process_news_ai` и `send_single_notification`)
- [ ] Глобальные exception handlers — сейчас только `LookupError`, нужно покрыть остальные
- [ ] ~~Sources API~~ ✅ готово — полный CRUD, не заглушка

---

## Безопасность

- [ ] `refresh_token` — хранить в `httpOnly cookie` вместо `localStorage` (сейчас в localStorage)
- [ ] Secrets management — убрать `.env.prod` из репо (уже закоммичен), хранить в GitHub Secrets

---

## ML (importance scoring)

- [ ] Собрать фичи: topic_scores, source_reach, reactions_count, hour_of_day
- [ ] Разметить вручную 200-300 новостей по важности (0.0 – 1.0)
- [ ] Обучить модель — заменить заглушку в `importance.py`
- [ ] Использовать `importance_score` как порог фильтрации в рассылке

---

## Производительность

- [ ] Кеш новостей в Redis — не ходить в БД при каждом запросе ленты
- [ ] React Query — заменить `useEffect + fetch` на `useQuery` / `useMutation`
- [ ] Error boundary — глобальный обработчик ошибок в React

---

## Бот

- [ ] `/settings` — inline клавиатуры для выбора топиков прямо в боте
- [ ] `/sources` — просмотр и управление источниками в боте
- [ ] Лимит уведомлений — не больше N в сутки на пользователя

---

## Настройки пользователя (фронт + бот)

- [ ] Тема оформления — светлая / тёмная / системная
- [ ] Шрифт — размер (S / M / L) и семейство (serif / sans-serif)
- [ ] Язык интерфейса — ru / en (i18n)

---

## Когда-нибудь

### Production readiness
- [ ] Multi-stage Dockerfile — уменьшить размер образа
- [ ] Структурированное логирование — loguru / structlog вместо print

### Новые фичи
- [ ] Deduplication новостей — один ивент от разных источников, группировка по URL + fuzzy match заголовка
- [ ] Digest (дайджест) — топ-N новостей за день/неделю в Telegram или на почту
- [ ] Read later — сохранить статью, отдельная вкладка во фронте
- [ ] Cursor-based пагинация — вместо OFFSET для relevance сортировки
