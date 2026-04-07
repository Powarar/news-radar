from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    # TODO: inline keyboard for topic preferences and source toggles
    await message.answer("Settings — coming soon.")


@router.message(Command("sources"))
async def cmd_sources(message: Message):
    # TODO: list sources with enable/disable buttons
    await message.answer("Sources — coming soon.")
