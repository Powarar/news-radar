import os

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, http_client: httpx.AsyncClient):
    telegram_id = str(message.from_user.id)
    resp = await http_client.post(
        "/api/bot/notifications",
        json={"telegram_id": telegram_id, "enabled": True},
        headers={"X-Bot-Token": BOT_TOKEN},
    )
    if resp.status_code == 200:
        await message.answer(
            "Уведомления включены. Новости по вашим темам будут приходить сюда.\n\n"
            "Настроить темы — в приложении."
        )
    elif resp.status_code == 404:
        await message.answer(
            "Аккаунт не найден. Войдите через приложение — оно привяжет ваш Telegram автоматически."
        )
    else:
        await message.answer("Что-то пошло не так, попробуйте позже.")


@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message, http_client: httpx.AsyncClient):
    telegram_id = str(message.from_user.id)
    resp = await http_client.post(
        "/api/bot/notifications",
        json={"telegram_id": telegram_id, "enabled": False},
        headers={"X-Bot-Token": BOT_TOKEN},
    )
    if resp.status_code == 200:
        await message.answer("Уведомления отключены. Включить снова — /subscribe")
    elif resp.status_code == 404:
        await message.answer(
            "Аккаунт не найден. Войдите через приложение — оно привяжет ваш Telegram автоматически."
        )
    else:
        await message.answer("Что-то пошло не так, попробуйте позже.")


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await message.answer(
        "<b>Настройки</b>\n\n"
        "/subscribe — включить уведомления о новостях\n"
        "/unsubscribe — отключить уведомления",
        parse_mode="HTML",
    )
