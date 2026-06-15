# TODO — News Radar

## Семантический поиск (~5–7 вечеров)

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

- [ ] Найти модель суммаризации которая не обрывает текст на полуслове (текущая `mT5_multilingual_XLSum` обрезает) — смотреть в сторону `facebook/bart-large-cnn` или `google/pegasus-xsum`
- [ ] Генерация заголовка если у новости нет title — отдельная HF-модель или prompt к суммаризатору
- [ ] Добавить больше источников — RSS и Telegram каналы на ru/en


## DevOps и деплой

- [ ] GitHub Actions — build + push Docker образов, SSH деплой на сервер при пуше в `main`
- [ ] Healthcheck в `docker-compose.prod.yml` (endpoint `/api/health` уже есть)
- [ ] SSL в nginx — Let's Encrypt / Certbot
- [ ] Flower — UI мониторинга Celery очередей
- [ ] Бэкапы PostgreSQL — pg_dump по крону

---

## Качество кода

- [ ] Тесты — pytest + httpx для auth endpoints
- [ ] Celery retry — `autoretry_for=(Exception,), retry_backoff=True` на задачах парсинга
- [ ] Глобальные exception handlers вместо try/except в каждом роуте
- [ ] Multi-stage Dockerfile — уменьшить размер образа бэкенда

---

## Безопасность

- [ ] `refresh_token` — хранить в `httpOnly cookie` вместо `localStorage`
- [ ] Secrets management — убрать `.env.prod` из репо, хранить в GitHub Secrets

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
