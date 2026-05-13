import os

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

router = Router()

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")


@router.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🌐 Открыть News Radar", web_app=WebAppInfo(url=FRONTEND_URL))
    ]])
    await message.answer(
        "Добро пожаловать в <b>News Radar</b>!\n\n"
        "Нажми кнопку — откроется приложение, войдёшь автоматически.",
        parse_mode="HTML",
        reply_markup=keyboard,
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
