# Database Schema

```mermaid
erDiagram
    users {
        int id PK
        string email
        string username
        string hashed_password
        string google_id
        string telegram_id
        bool is_active
        bool notifications_enabled
        string plan
        datetime subscription_expires_at
        string language
        string country
        datetime created_at
    }

    sources {
        int id PK
        string name
        string url
        string type
        string language
        string country
        text topics
        bool is_active
        int fetch_interval_minutes
        datetime last_fetched_at
        datetime created_at
    }

    news_items {
        int id PK
        int source_id FK
        text title
        text body
        text summary
        string url
        string image_url
        string language
        text topics
        float importance_score
        datetime published_at
        datetime created_at
    }

    user_topic_preferences {
        int id PK
        int user_id FK
        string topic
        float weight
    }

    user_source_settings {
        int id PK
        int user_id FK
        int source_id FK
        bool enabled
        bool blacklisted
    }

    news_reactions {
        int id PK
        int user_id FK
        int news_item_id FK
        string reaction
        datetime created_at
    }

    users ||--o{ user_topic_preferences : "предпочтения"
    users ||--o{ user_source_settings : "настройки источников"
    users ||--o{ news_reactions : "реакции"
    sources ||--o{ news_items : "новости"
    sources ||--o{ user_source_settings : "настройки"
    news_items ||--o{ news_reactions : "реакции"
```

## Связи

| Таблица | С кем | Тип | Смысл |
|---|---|---|---|
| `users` → `user_topic_preferences` | один ко многим | пользователь выбирает веса тем |
| `users` → `user_source_settings` | один ко многим | пользователь включает/скрывает источники |
| `users` → `news_reactions` | один ко многим | пользователь ставит like/dislike/blacklist |
| `sources` → `news_items` | один ко многим | источник публикует новости |
| `sources` → `user_source_settings` | один ко многим | настройки источника для каждого юзера |
| `news_items` → `news_reactions` | один ко многим | у новости много реакций от разных юзеров |
