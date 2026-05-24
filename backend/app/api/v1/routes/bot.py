from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.news import ReactionType
from app.repositories.news import NewsRepository
from app.repositories.user import UserRepository
from app.services.news import NewsService

router = APIRouter()


def verify_bot_token(request: Request) -> None:
    token = request.headers.get("X-Bot-Token", "")
    if not settings.telegram_bot_token or token != settings.telegram_bot_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bot token")


BotAuth = Annotated[None, Depends(verify_bot_token)]


class BotReactRequest(BaseModel):
    telegram_id: str
    news_id: int
    reaction: ReactionType


class BotNotificationsRequest(BaseModel):
    telegram_id: str
    enabled: bool


@router.post("/react")
async def bot_react(
    data: BotReactRequest,
    _: BotAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await UserRepository(db).get_by_telegram_id(data.telegram_id)
    if not user:
        raise HTTPException(404, "User not found")
    news_repo = NewsRepository(db)
    await NewsService(db).react(user.id, data.news_id, data.reaction)
    counts = await news_repo.get_reaction_counts(data.news_id)
    return {"ok": True, **counts}


@router.post("/notifications")
async def bot_set_notifications(
    data: BotNotificationsRequest,
    _: BotAuth,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    repo = UserRepository(db)
    user = await repo.get_by_telegram_id(data.telegram_id)
    if not user:
        raise HTTPException(404, "User not found")
    await repo.update(user, {"notifications_enabled": data.enabled})
    return {"ok": True, "notifications_enabled": data.enabled}
