# Как работает авторизация через Telegram

## Проблема

HTTP — протокол без состояния. Каждый запрос сервер получает "с нуля" и не знает кто его делает.
Чтобы сервер понял кто ты, клиент при каждом запросе присылает JWT-токен в заголовке:

```
Authorization: Bearer eyJhbGci...
```

Задача: пользователь открывает сайт из Telegram и уже залогинен — без кнопок, без форм.

---

## Как открывается приложение из Telegram

Кнопка с типом `web_app` в боте открывает сайт внутри Telegram в специальном WebView.
Telegram **сам вставляет** в страницу объект `window.Telegram.WebApp` с данными пользователя.

---

## Mini App (основной сценарий)

Когда кнопка в боте имеет тип `web_app` — Telegram открывает Mini App.

### Что такое initData

В момент нажатия кнопки **серверы Telegram** генерируют строку `initData`:

```
user=%7B%22id%22%3A123456789%2C%22username%22%3A%22pavel%22%7D&auth_date=1747123456&hash=a3f9c2...
```

После URL-декодирования:

```
user      = {"id": 123456789, "username": "pavel", "first_name": "Pavel"}
auth_date = 1747123456   ← unix timestamp когда Telegram это сгенерировал
hash      = a3f9c2...    ← криптографическая подпись
```

Эту строку Telegram вставляет в `window.Telegram.WebApp.initData` внутри WebView.
**Пользователь не создаёт её и не может изменить** — она пришла с серверов Telegram.

### Почему нельзя просто доверять initData

Любой может сделать POST-запрос на бэкенд с произвольными данными:

```json
{"init_data": "user={\"id\":1}&auth_date=9999999999&hash=abcd"}
```

Нужно проверить что данные реально пришли от Telegram, а не придуманы. Для этого есть `hash`.

### Как Telegram считает hash

Telegram использует двойной HMAC-SHA256:

```
Шаг 1: secret = HMAC-SHA256(key="WebAppData", data=bot_token)
Шаг 2: hash   = HMAC-SHA256(key=secret, data=check_string)
```

`check_string` — все поля кроме hash, отсортированные по алфавиту, через \n:
```
auth_date=1747123456
user={"id": 123456789, "username": "pavel"}
```

Токен бота знают только Telegram и владелец бота. Пользователь не знает токен → не может посчитать правильный hash → не может подделать данные.

### Почему двойной HMAC, а не SHA256(bot_token + данные)?

Атака на длину (length extension attack): зная `SHA256(secret + данные)` и длину `secret`,
можно дописать произвольные данные в конец и посчитать валидный хэш без знания секрета.
HMAC структурно защищает от этого — дописать данные не поможет.

### Почему ключ именно "WebAppData"

У Telegram есть несколько контекстов авторизации через один и тот же бот:

| Контекст    | Формула секрета              |
|-------------|------------------------------|
| Login Widget (кнопка на сайте) | `SHA256(bot_token)` |
| Mini App initData              | `HMAC("WebAppData", bot_token)` |

Разные формулы → разные секреты → нельзя взять подпись из одного контекста и использовать в другом.

### Почему compare_digest вместо ==

```python
# Уязвимо к timing attack:
if computed == received_hash:

# Безопасно:
if hmac.compare_digest(computed, received_hash):
```

Обычное сравнение строк в Python прерывается на первом несовпадающем символе.
Атакующий делает тысячи запросов и по времени ответа понимает сколько символов угадал правильно.
`compare_digest` всегда проходит строку до конца — время одинаковое независимо от совпадения.

### Проверка auth_date

```python
if time.time() - int(params.get("auth_date", 0)) > 600:
    return None
```

`initData` действительна 10 минут. Иначе: кто-то перехватил чужой `initData` сейчас,
подождал — и использует его завтра. С проверкой через 10 минут данные протухают.

---

## Полный поток Mini App

```
Пользователь нажимает кнопку web_app в боте
        ↓
Telegram серверы генерируют initData:
  user={"id":123456789, ...}
  auth_date=1747123456
  hash=<HMAC подпись>
        ↓
Telegram открывает news.safonovpavel.space в WebView
Вставляет window.Telegram.WebApp.initData = "..."
        ↓
React загружает App, вызывается useTelegramWebApp()
  Проверяет: есть initData? нет токена в localStorage?
  tg.ready() — сообщает Telegram что страница загрузилась
        ↓
POST /api/v1/auth/telegram/webapp
  {"init_data": "user=...&auth_date=...&hash=..."}
        ↓
verify_webapp_init_data():
  1. parse_qsl() парсит и URL-декодирует строку
  2. Вынимает hash из словаря
  3. Проверяет auth_date — не старше 10 минут?
  4. Собирает check_string из оставшихся полей
  5. Считает secret = HMAC("WebAppData", bot_token)
  6. Считает computed = HMAC(secret, check_string)
  7. compare_digest(computed, hash) — совпадает?
  8. Возвращает распарсенный user = {"id": 123456789, ...}
        ↓
telegram_webapp_login():
  Ищет юзера по telegram_id в БД
  Нет юзера → создаёт с username = tg_123456789
  Генерирует JWT access_token (24ч) + refresh_token (30д)
        ↓
Фронтенд получает токены
localStorage ← токены
window.location.replace("/feed")
        ↓
Страница перезагружается
useUser() видит токен → GET /api/v1/users/me → рендерит ленту
Пользователь залогинен
```

---

## Почему web_app кнопка, а не url кнопка

```python
# url= открывает браузер. initData нет. Mini App не запускается.
InlineKeyboardButton(url="https://news.safonovpavel.space")

# web_app= открывает Mini App. initData есть. Авто-логин работает.
InlineKeyboardButton(web_app=WebAppInfo(url="https://news.safonovpavel.space"))
```

Это разные типы кнопок в Telegram Bot API. Первая просто открывает ссылку.
Вторая говорит Telegram "открой как Mini App, сгенерируй initData и передай его странице".

---

## Где какой файл

| Файл | Что делает |
|------|-----------|
| `bot/handlers/news.py` | `/start` — отправляет кнопку с web_app |
| `backend/app/core/security.py` | `verify_webapp_init_data()` — проверяет подпись |
| `backend/app/services/auth.py` | `telegram_webapp_login()` — находит/создаёт юзера |
| `backend/app/api/v1/routes/auth.py` | `POST /telegram/webapp` — точка входа |
| `frontend/src/App.tsx` | `useTelegramWebApp()` — хук, запускает всё на фронте |
