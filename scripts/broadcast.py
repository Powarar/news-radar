#!/usr/bin/env python3
"""
Рассылка сообщения пользователям.

Запуск (всем у кого есть telegram_id):
    docker compose exec backend python /app/scripts/broadcast.py "Текст"

Запуск только подписанным:
    docker compose exec backend python /app/scripts/broadcast.py "Текст" --subscribed
"""
import sys
import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "/app")

from app.core.config import settings
from app.models.user import User
from app.models.news import NewsItem, NewsReaction  # noqa: F401
from app.models.source import Source  # noqa: F401


def main():
    if len(sys.argv) < 2:
        print("Использование: broadcast.py <текст сообщения>")
        sys.exit(1)

    text = sys.argv[1]
    only_subscribed = "--subscribed" in sys.argv

    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(engine)

    with Session() as session:
        query = select(User.telegram_id).where(User.telegram_id.isnot(None))
        if only_subscribed:
            query = query.where(User.notifications_enabled)
        users = session.execute(query).scalars().all()

    if not users:
        print("Нет пользователей для рассылки.")
        return

    print(f"Отправляю {len(users)} пользователям...")

    ok, failed = 0, 0
    with httpx.Client(timeout=10) as client:
        for telegram_id in users:
            resp = client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": telegram_id, "text": text, "parse_mode": "HTML"},
            )
            if resp.status_code == 200:
                ok += 1
            else:
                failed += 1
                print(f"  ошибка {telegram_id}: {resp.text}")

    print(f"Готово: {ok} доставлено, {failed} ошибок.")


if __name__ == "__main__":
    main()
