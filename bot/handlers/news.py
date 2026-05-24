import os

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

router = Router()

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


def news_keyboard(news_id: int, likes: int = 0, dislikes: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"↑ {likes}", callback_data=f"like:{news_id}"),
            InlineKeyboardButton(text=f"↓ {dislikes}", callback_data=f"dislike:{news_id}"),
            InlineKeyboardButton(text="✖", callback_data=f"blacklist:{news_id}"),
        ],
    ])


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
async def cmd_malayatokmachka(message: Message):
    await message.answer("⚡️Сегодня Малая Токмачка не взята")


@router.message(Command("top"))
async def cmd_top(message: Message, http_client: httpx.AsyncClient):
    response = await http_client.get("/api/v1/news/", params={"limit": 5})

    if response.status_code != 200:
        await message.answer("Не удалось загрузить новости.")
        return

    news_items = response.json().get("items", [])
    if not news_items:
        await message.answer("Новостей пока нет.")
        return

    for item in news_items:
        parts = []
        if item.get("title"):
            parts.append(f"<b>{item['title']}</b>")
        text_body = item.get("summary") or item.get("body") or ""
        if text_body:
            parts.append(text_body[:500])
        if item.get("url"):
            parts.append(f'<a href="{item["url"]}">Читать далее</a>')

        await message.answer(
            "\n\n".join(parts) if parts else "—",
            parse_mode="HTML",
            reply_markup=news_keyboard(item["id"]),
            disable_web_page_preview=True,
        )


@router.callback_query(F.data.regexp(r"^(like|dislike|blacklist):\d+$"))
async def handle_reaction(callback: CallbackQuery, http_client: httpx.AsyncClient):
    action, news_id = callback.data.split(":")
    telegram_id = str(callback.from_user.id)

    resp = await http_client.post(
        "/api/bot/react",
        json={"telegram_id": telegram_id, "news_id": int(news_id), "reaction": action},
        headers={"X-Bot-Token": BOT_TOKEN},
    )

    if resp.status_code == 404:
        await callback.answer("Войди в приложение — оно привяжет твой аккаунт.")
        return
    if resp.status_code != 200:
        await callback.answer("Что-то пошло не так.")
        return

    data = resp.json()
    likes, dislikes = data["likes"], data["dislikes"]

    labels = {
        "like": f"↑ {likes}",
        "dislike": f"↓ {dislikes}",
        "blacklist": "источник скрыт",
    }
    await callback.answer(labels.get(action, "OK"))
    await callback.message.edit_reply_markup(
        reply_markup=news_keyboard(int(news_id), likes, dislikes)
    )
