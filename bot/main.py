import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from handlers import news, settings

load_dotenv()

bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(news.router)
dp.include_router(settings.router)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
