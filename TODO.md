# TODO — News Radar

---

- [ ] CORS — убрать `allow_origins=["*"]`, прописать конкретные домены

---

## Шаг 2 — MVP (минимально рабочее приложение)

- [ ] `GET /preferences/` — вернуть топики пользователя с весами
- [ ] `PUT /preferences/` — обновить веса топиков
- [ ] `GET /news/` — добавить фильтрацию по предпочтениям пользователя и языку
- [V] `classifier.py` — HTTP вызов HuggingFace Inference API (`facebook/bart-large-mnli`)
- [ ] `summarizer.py` — HTTP вызов HuggingFace Inference API (`csebuetnlp/mT5_multilingual_XLSum`)
- [ ] `importance.py` — формула: `max_topic * 0.6 + log(reach) * 0.3 + reactions * 0.1`
- [ ] `process_news_ai()` task — вызвать classifier + summarizer + importance, сохранить в `NewsItem`
- [ ] Индексы в БД — добавить на `news_items.published_at`, `news_items.language`
- [ ] Frontend: страница предпочтений — выбор топиков и весов (слайдеры)
- [ ] Frontend: token refresh flow — retry с `refresh_token` при 401 вместо сразу логаута

---

## Шаг 3 — Полный функционал

- [ ] `POST /news/{id}/react` — like / dislike / blacklist
- [ ] Unique constraint `(user_id, news_item_id)` на `news_reactions`
- [ ] `GET /sources/` — список источников с настройками пользователя
- [ ] `POST /sources/` — добавить источник
- [ ] `PATCH /sources/{id}/toggle` — включить/выключить источник для себя
- [ ] `PATCH /sources/{id}/blacklist` — заблокировать источник
- [ ] `send_notifications()` task — найти юзеров по топикам, отправить через бота
- [ ] Rate limiting на `/login` и `/register`
- [ ] Frontend: реакции на карточке новости — кнопки like / dislike / blacklist
- [ ] Frontend: страница источников — список с переключателями

---

## Шаг 4 — Telegram Bot

- [ ] `/top` — запрос к API, отправить топ-5 новостей
- [ ] `/settings` — inline клавиатуры для выбора топиков
- [ ] `/sources` — просмотр и управление источниками

---

## Шаг 5 — DevOps и деплой

- [ ] Healthcheck в `docker-compose.prod.yml` (endpoint `/api/health` уже есть)
- [ ] GitHub Actions — build + push Docker образов, SSH деплой на сервер при пуше в `main`
- [ ] Настроить пользователя `deploy` на сервере (без root)
- [ ] SSL в nginx — Let's Encrypt / Certbot
- [ ] Flower — UI мониторинга Celery очередей (добавить в docker-compose)
- [ ] Логирование — structured logs через `loguru`, отдельный volume
- [ ] Бэкапы PostgreSQL — pg_dump по крону

---

## Шаг 6 — Качество кода

- [ ] Тесты — pytest + httpx для auth endpoints (register, login, logout, refresh)
- [ ] Глобальные exception handlers (`@app.exception_handler`) вместо try/except в каждом роуте
- [ ] Middleware — логирование времени каждого запроса
- [ ] Dependency injection — вынести pagination (limit/offset) в общую зависимость
- [ ] Celery retry — `autoretry_for=(Exception,), retry_backoff=True` на задачах парсинга
- [ ] Multi-stage Dockerfile — уменьшить размер образа бэкенда
- [ ] `.dockerignore` — не тянуть `.venv`, `__pycache__`, `.env` в образ

---

## Шаг 7 — Безопасность

- [ ] `refresh_token` — хранить в `httpOnly cookie` вместо `localStorage` (защита от XSS)
- [ ] CSRF токен при переходе на cookie
- [ ] Secrets management — убрать `.env.prod` из репо, хранить в GitHub Secrets / Vault
- [ ] Добавить `Helmet` / security headers в nginx (X-Frame-Options, CSP и др.)

---

## Шаг 8 — Производительность и масштаб

- [ ] Кеш новостей в Redis — не ходить в БД при каждом запросе ленты
- [ ] React Query — заменить `useEffect + fetch` на `useQuery` / `useMutation`
- [ ] Кастомные хуки — вынести логику из компонентов (`useAuth`, `useFeed`, `usePreferences`)
- [ ] Оптимистичные обновления — реакция применяется сразу, без ожидания сервера
- [ ] `select_in_loading` вместо `joined_loading` где есть N+1 запросы
- [ ] Error boundary — глобальный обработчик ошибок в React UI
- [ ] PWA — проверить что манифест и service worker работают корректно
