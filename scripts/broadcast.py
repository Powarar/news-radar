#!/usr/bin/env python3
"""
Рассылка сообщения всем подписанным пользователям.

Запуск:
    docker compose exec backend python /app/scripts/broadcast.py "Текст сообщения"
"""
import sys
import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "/app")

from app.core.config import settings
from app.models.user import User


def main():
    if len(sys.argv) < 2:
        print("Использование: broadcast.py <текст сообщения>")
        sys.exit(1)

    text = sys.argv[1]

    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(engine)

    with Session() as session:
        users = session.execute(
            select(User.telegram_id).where(
                User.telegram_id.isnot(None),
                User.notifications_enabled == True,
            )
        ).scalars().all()

    if not users:
        print("Нет подписанных пользователей.")
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
