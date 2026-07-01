# Как работает News Radar

## Что сделали сегодня

### Проблема 1: уведомления за старые новости

Когда воркер не работал (например, упал или ещё не запустился), задачи на отправку
уведомлений накапливались в очереди Redis. При перезапуске воркер разгребал всё это
и слал уведы за вчерашние новости.

**Решение** — добавили проверку возраста в `send_notifications`:

```python
news_time = news.published_at or news.created_at
if news_time and datetime.now(timezone.utc) - news_time > timedelta(hours=2):
    logger.info("Skipping notification for old news_id=%d", news_item_id)
    return
```

Если новость старше 2 часов — молча пропускаем.

Дополнительно: перед перезапуском воркера нужно чистить очередь Redis, чтобы
накопившиеся задачи не обрабатывались вообще:

```bash
docker-compose -f docker-compose.prod.yml exec redis redis-cli del parsing ai notifications preferences default celery
```

---

### Проблема 2: пустые уведомления из Telegram-каналов

Посты в Telegram-каналах не имеют заголовка — только тело поста. Раньше код делал:

```python
title = news.title or "Без заголовка"
```

И приходило сообщение вида:
```
Без заголовка
Темы: politics: 90%

Подробнее: https://t.me/...
```

Никакого содержания. **Решение** — если заголовка нет, берём первые 160 символов тела:

```python
title = news.title or ""
if not title and news.body:
    title = news.body[:160].rstrip()
    if len(news.body) > 160:
        title += "…"
title = title or "Без заголовка"

# Summary показываем только если есть настоящий заголовок
# (для TG-постов тело уже в заголовке — дублировать не нужно)
summary_line = f"\n\n{news.summary}" if news.summary and news.title else ""
```

---

## Лента: три режима сортировки

### "Новые" (date)

Чистая хронология. Берём `published_at` (дата из источника) или `created_at`
(когда мы сохранили) — что есть — и сортируем по убыванию.

```python
date_sort = func.coalesce(NewsItem.published_at, NewsItem.created_at)
order_by = [desc(date_sort)]
```

Без персонализации. Для гостей это единственный доступный режим.

---

### "Важные" (importance)

Сортировка по `importance_score` — числовое поле на каждой новости.

```python
order_by = [desc(func.coalesce(NewsItem.importance_score, 0.0)), desc(date_sort)]
```

`importance_score` считается в `services/ai/importance.py`. **Сейчас это заглушка**
— все новости получают одинаковый балл. Это TODO: нужна реальная формула,
которая учитывает например количество источников об одном событии, вес топика.

---

### "Для вас" (relevance)

Самый сложный режим. Только для авторизованных. Три шага:

#### Шаг 1 — Убираем заблокированные источники

Если пользователь нажал ✖ на карточке — источник попадает в `user_source_settings`
с `blacklisted = true`. Они фильтруются подзапросом:

```python
blacklisted_sq = (
    select(UserSourceSetting.source_id)
    .where(UserSourceSetting.user_id == user_id, UserSourceSetting.blacklisted)
    .scalar_subquery()
)
stmt = stmt.where(NewsItem.source_id.not_in(blacklisted_sq))
```

#### Шаг 2 — Исключаем "Не читаю" топики

Если пользователь поставил топику вес = 0, новость скрывается, если этот топик
**доминирует** в новости (уверенность классификатора > 0.5).

Пример: пользователь не читает политику.
- `{politics: 0.8}` → скрыта (политика доминирует)
- `{politics: 0.3, technology: 0.7}` → показана (политика не доминирует)

```python
for topic in excluded:
    stmt = stmt.where(
        or_(
            NewsItem.topics.is_(None),
            ~topics_jsonb.has_key(topic),
            cast(topics_jsonb[topic].as_string(), Float) <= 0.5,
        )
    )
```

#### Шаг 3 — Считаем релевантность

У каждого пользователя есть таблица `user_topic_preferences` с весами 0.0–1.0:

| topic      | weight |
|------------|--------|
| technology | 0.8    |
| science    | 0.6    |
| politics   | 0.0    |

У каждой новости есть `topics` — JSON с уверенностью классификатора:
```json
{"technology": 0.9, "business": 0.4}
```

**Формула релевантности:**
```
relevance = Σ (user_weight[topic] × news_score[topic])
```

Для примера выше:
```
relevance = 0.8 × 0.9 + 0 × 0.4 = 0.72
```

В SQL это выглядит так:
```python
score_parts = [
    case(
        (topics_jsonb.has_key(topic), weight * cast(topics_jsonb[topic].as_string(), Float)),
        else_=literal(0.0),
    )
    for topic, weight in prefs.items()
]
relevance = score_parts[0]
for part in score_parts[1:]:
    relevance = relevance + part
```

Новости с `relevance < 0.05` отрезаются — чтобы не показывать совсем нерелевантное.

#### Шаг 4 — Сортировка

```python
day_bucket = func.date_trunc("day", date_sort)
order_by = [desc(day_bucket), desc(date_sort), desc(relevance)]
```

Сначала группируем по **дню** (сегодня > вчера), внутри дня — по **времени**,
а не по релевантности. Это важно: если сортировать только по релевантности,
весь топ будет заполнен одной темой которую ты любишь, а свежие новости
других тем уйдут вниз.

---

## Как накапливаются предпочтения

При каждой реакции запускается фоновая задача `update_topic_preferences`:

```python
delta = 0.1 if reaction == "like" else -0.1

for topic, score in news_topics.items():
    if score < 0.3:
        continue  # слабые топики не учитываем
    pref.weight = max(0.0, min(1.0, pref.weight + delta * score))
```

Вес меняется пропорционально уверенности классификатора. Лайкнул новость
с `{technology: 0.9}` → вес технологий +0.09. Дизлайкнул → -0.09.
Вес зажат в [0.0, 1.0].

Новый пользователь без предпочтений получает хронологию, пока не наберёт
достаточно реакций.

---

## Telegram-уведомления

### Пайплайн

```
fetch_sources (каждые 15 мин, beat)
    └─ fetch_telegram_channel / fetch_website
           └─ process_news_ai
                  └─ send_notifications
                         └─ send_single_notification (per user)
```

### Кто получает

```python
# Берём всех пользователей с Telegram и включёнными уведомлениями
all_users = session.execute(
    select(User.id, User.telegram_id)
    .where(User.telegram_id.isnot(None), User.notifications_enabled)
).all()

# Для каждого пользователя проверяем предпочтения
prefs = user_topics.get(user_id)
if prefs:
    # Должен совпасть хотя бы один любимый топик с уверенностью > 20%
    matching = [t for t in prefs if t in news_topics and news_topics[t] > 0.2]
    if not matching:
        continue
# Нет предпочтений → новый подписчик, получает всё
```

### Что не приходит

- Новости без топиков (классификатор не смог определить тему)
- Новости старше 2 часов (защита от флуда при перезапуске воркера)

### Что в сообщении

```
<b>Первые 160 символов поста</b>          ← для TG-каналов (нет заголовка)
<b>Заголовок статьи</b>                    ← для сайтов

Темы: politics: 90%, military: 70%

Краткое содержание...                      ← только для сайтов с заголовком

Подробнее: https://...

[ ↑ 3 ]  [ ↓ 1 ]  [ ✖ ]                  ← инлайн-кнопки
```

Кнопки работают прямо в Telegram: лайк/дизлайк обновляют предпочтения,
✖ блокирует источник.
