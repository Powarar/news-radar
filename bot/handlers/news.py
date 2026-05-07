import os 

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from httpx import AsyncClient

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Welcome to News Radar!\n\n"
        "I'll send you personalized news based on your preferences.\n\n"
        "Use /settings to configure topics and sources."
    )

@router.message(Command("malayatokmachka"))
async def cmd_start(message: Message):
    await message.answer(
        "⚡️Сегодня Малая Токмачка не взята"
    )

@router.message(Command("top"))
async def cmd_top(message: Message):
    async with AsyncClient() as client:
        response = await client.get(
            os.environ.get('BACKEND_URL', 'http://backend:8000') + '/api/v1/news/',
            params={"limit": 5},
        )

    if response.status_code != 200:
        await message.answer("Failed to fetch news.")
        return

    news_items = response.json().get('items', [])
    if not news_items:
        await message.answer("No news found.")
        return

    for item in news_items:
        parts = []
        if item.get('title'):
            parts.append(item['title'])
        text_body = item.get('summary') or item.get('body') or ''
        if text_body:
            parts.append(text_body[:500])
        if item.get('url'):
            parts.append(item['url'])
        if parts:
            await message.answer('\n'.join(parts))
