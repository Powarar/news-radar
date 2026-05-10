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