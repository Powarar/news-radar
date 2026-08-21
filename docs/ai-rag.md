# AI и RAG в News Radar

## Коротко

В проекте есть два разных AI-контура:

1. Фоновая обработка каждой новости: Groq классифицирует темы и пишет краткое
   резюме, затем Celery рассчитывает важность и индексирует новость в Qdrant.
2. RAG-чат: вопрос пользователя превращается в вектор, Qdrant находит близкие
   свежие новости, а Groq формирует ответ только по найденному контексту.

RAG (Retrieval-Augmented Generation) — это «генерация с поиском». Языковая
модель не ищет новости сама. Сначала приложение достаёт подходящие документы из
векторной базы, затем вставляет их в prompt и просит модель ответить только по ним.

## Где находится код

| Часть | Файл или каталог | Назначение |
| --- | --- | --- |
| Сбор новостей и оркестрация | `backend/app/workers/tasks.py` | Celery-задачи парсинга, AI-обработки и индексации |
| Классификация и summary | `backend/app/services/ai/pipeline.py` | Один запрос к Groq, fallback моделей и keyword fallback |
| Запасной классификатор | `backend/app/services/ai/keyword_classifier.py` | Темы по словарям, если LLM недоступна |
| Оценка важности | `backend/app/services/ai/importance.py` | Percentile по последним 200 новостям |
| HTTP-клиент embeddings | `backend/app/services/ai/embedding.py` | Запрос в embedding-service и запись в Qdrant |
| Embedding-сервис | `embedding-service/app/main.py` | Одна модель, batch API, SQLite-кеш, healthcheck |
| RAG-поиск и генерация | `backend/app/services/ai/news_chat.py` | Векторизация вопроса, поиск Qdrant, prompt для Groq |
| HTTP endpoint чата | `backend/app/api/v1/routes/news.py` | `POST /api/v1/news/chat` |
| Векторное хранилище | volume `qdrant_data` | Коллекция Qdrant `news_feed` |
| Кеш embeddings | volume `embedding_data` | Модель и SQLite `result-cache/embeddings.sqlite3` |

Отдельной папки с «файлами RAG» нет: RAG — это весь маршрут из
`news_chat.py`, embedding-service, Qdrant и Groq. В репозитории находится код,
а сами векторы живут в Docker volume `qdrant_data`.

## Путь новой новости

1. Celery Beat каждые 15 минут запускает `fetch_sources`.
2. Парсеры Telegram/RSS/Web создают `NewsItem` в PostgreSQL со статусом
   `pending` и ставят `process_news_ai(news_id)` в очередь `ai`.
3. `pipeline.process` отправляет заголовок и текст в Groq. System prompt просит
   вернуть JSON с темами и русским summary. Ответ валидируется Pydantic; лишние
   темы и оценки вне диапазона отбрасываются.
4. При недоступности Groq перебираются резервные модели. Полный сбой включает
   локальный keyword-классификатор; Celery повторяет неуспешную задачу.
5. Темы и summary сохраняются в PostgreSQL. Важность считается не LLM: для
   каждой темы берётся доля последних новостей с меньшей оценкой, затем лучший
   percentile умножается на `0.8`.
6. Для успешной новости запускается `index_news_vector`. Backend отправляет
   `title + body` в embedding-service.
7. Embedding-service считает SHA-256 от имени модели и текста. Готовый вектор
   берётся из SQLite или вычисляется единственной загруженной multilingual
   моделью. И модель, и результат переживают рестарты благодаря volume.
8. Backend записывает 768-мерный вектор в Qdrant `news_feed`. Payload содержит
   исходный title/body, summary и Unix-время публикации; ID точки равен ID
   новости из PostgreSQL.

PostgreSQL — источник истины для новостей, пользователей, реакций и настроек.
Qdrant — производный поисковый индекс: его можно пересобрать из PostgreSQL.
Redis — брокер Celery и служебное хранилище, но не база RAG.

## Как ищется похожесть

`fetch_news_context` в `news_chat.py` выполняет следующие шаги:

1. Вопрос пользователя кодируется той же embedding-моделью, что и новости.
2. Qdrant сравнивает вопрос с векторами новостей по cosine similarity. Чем
   ближе направление двух векторов, тем выше смысловая похожесть; точное
   совпадение слов не обязательно, и multilingual-модель сопоставляет запросы
   на разных языках.
3. Фильтр `published_at >= now - days` исключает старые новости.
4. `score_threshold=0.35` отсекает слабые совпадения, `limit=5` оставляет до
   пяти лучших результатов.
5. Из payload строятся блоки «дата, заголовок, суть». Это retrieved context.

Prompt не выполняет similarity-поиск. Поиск уже сделал Qdrant. Prompt получает
готовые результаты и содержит ограничения: русский язык, только факты из
контекста, без выдумывания и честный ответ при отсутствии данных. Температура
`0.2` уменьшает вариативность, но фактическая защита прежде всего зависит от
качества retrieved context и соблюдения инструкции моделью.

## Embedding API и кеш

Сервис поднимает ровно один Uvicorn worker и одну модель
`sentence-transformers/paraphrase-multilingual-mpnet-base-v2` размерности 768.

- `POST /v1/embeddings` — принимает `{"texts": ["..."]}` (до 32 текстов);
- `GET /health/live` — процесс работает;
- `GET /health/ready` — модель полностью загружена и сервис готов;
- `/data/model-cache` — скачанные файлы модели;
- `/data/result-cache/embeddings.sqlite3` — постоянный кеш готовых векторов.

Ключ кеша включает имя модели. Поэтому смена модели не вернёт старый
несовместимый вектор. Backend дополнительно проверяет размерность и количество
полученных векторов. Compose не запускает backend/worker до успешного readiness.

## Что является prompt, а что — моделью

- Embedding-модель не читает prompt и не генерирует текст. Она только переводит
  текст в числовой вектор.
- Qdrant не является AI-моделью. Он хранит векторы и быстро сортирует их по
  близости.
- Groq предоставляет генеративные модели. В `pipeline.py` prompt задаёт формат
  классификации/summary, в `news_chat.py` — правила ответа по RAG-контексту.
- `keyword_classifier.py` вообще не использует нейросеть: ищет основы слов и
  выдаёт детерминированные оценки.

## Эксплуатация

Проверка сервиса внутри Compose:

```bash
docker compose exec embedding-service python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8001/health/ready').read().decode())"
```

Проверка кеша: два одинаковых запроса дадут `cached: false`, затем
`cached: true`. Удаление контейнера кеш не удаляет; удаление Docker volume
`embedding_data` удаляет и модель, и рассчитанные embeddings. Qdrant volume
`qdrant_data` управляется отдельно.
