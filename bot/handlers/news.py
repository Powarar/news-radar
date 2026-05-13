import os

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from httpx import AsyncClient

router = Router()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


async def _get_magic_link(telegram_id: str) -> str | None:
    try:
        async with AsyncClient() as client:
            r = await client.post(
                f"{BACKEND_URL}/api/v1/auth/telegram/magic-link",
                json={"telegram_id": telegram_id},
                headers={"X-Bot-Token": BOT_TOKEN},
                timeout=5,
            )
        if r.status_code == 200:
            return f"{FRONTEND_URL}/tg-auth?code={r.json()['code']}"
    except Exception:
        pass
    return None


@router.message(Command("start"))
async def cmd_start(message: Message):
    link = await _get_magic_link(str(message.from_user.id))

    if link:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🌐 Открыть приложение", url=link)
        ]])
        await message.answer(
            "Добро пожаловать в <b>News Radar</b>!\n\n"
            "Нажми кнопку — ты автоматически войдёшь в веб-приложение.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await message.answer(
            "Добро пожаловать в News Radar!\n\n"
            "Используй /top для топ новостей."
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
