from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Welcome to News Radar!\n\n"
        "I'll send you personalized news based on your preferences.\n\n"
        "Use /settings to configure topics and sources."
    )


@router.message(Command("top"))
async def cmd_top(message: Message):
    # TODO: fetch top news from API, send as formatted messages
    await message.answer("Fetching top news...")
