import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await message.answer("Settings — coming soon.")


@router.message(Command("sources"))
async def cmd_sources(message: Message):
    await message.answer("Sources — coming soon.")

@router.message(Command("liana"))
async def cmd_liana(message: Message):
    frames = [
        "💛",
        "🧡",
        "❤️",
        "❤️‍🔥",
        "💖",
        "💗",
        "💓",
        "💞",
        "💝",
    ]

    sent = await message.answer("💛")

    for frame in frames[1:]:
        await asyncio.sleep(0.4)
        await sent.edit_text(frame)

    await asyncio.sleep(0.5)
    await sent.edit_text("💝 люблю кого-то сина сина 💝")