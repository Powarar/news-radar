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


@router.message(Command("top"))
async def cmd_top(message: Message):

    await message.answer("Fetching top news...")
    async with AsyncClient() as client:
        response = await client.get(os.environ.get('BACKEND_URL', 'http://backend:8000') + '/api/v1/news?limit=5')
        if response.status_code == 200:
            news_items = response.json().get('items', [])
            if news_items:
                for item in news_items:
                    parts = []
                    if item.get('title'):                                                                                                                             
                        parts.append(item['title'])
                    parts.append(item.get('summary') or item.get('body', ''))                                                                                         
                    if item.get('url'):
                        parts.append(item['url'])
                    text = '\n'.join(parts) 
                    await message.answer(text)
            else:
                await message.answer("No news found.")
