# TODO — News Radar

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
