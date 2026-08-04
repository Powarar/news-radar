import asyncio
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

import httpx
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from dotenv import load_dotenv
from handlers import news, settings

load_dotenv()

bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(news.router)
dp.include_router(settings.router)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")

COMMANDS = [
    BotCommand(command="start",       description="Запустить бота"),
    BotCommand(command="news",        description="Последние новости"),
    BotCommand(command="subscribe",   description="Включить уведомления"),
    BotCommand(command="unsubscribe", description="Выключить уведомления"),
    BotCommand(command="settings",    description="Настройки тем"),
    BotCommand(command="sources",     description="Управление источниками"),
    BotCommand(command="help",        description="Помощь"),
]


async def main():
    await bot.set_my_commands(COMMANDS)
    async with httpx.AsyncClient(base_url=BACKEND_URL) as http_client:
        await dp.start_polling(bot, http_client=http_client)


if __name__ == "__main__":
    asyncio.run(main())
