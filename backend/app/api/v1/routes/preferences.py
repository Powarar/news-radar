from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser
from app.core.database import get_db
from app.repositories.preferences import PreferencesRepository
from app.schemas.preferences import (
    VALID_TOPICS,
    PreferencesResponse,
    PreferencesUpdate,
    TopicPreference,
)

router = APIRouter()


def get_prefs_repo(db: Annotated[AsyncSession, Depends(get_db)]) -> PreferencesRepository:
    return PreferencesRepository(db)


@router.get("/", response_model=PreferencesResponse)
async def get_preferences(
    user: CurrentUser,
    repo: Annotated[PreferencesRepository, Depends(get_prefs_repo)],
):
    user_with_prefs = await repo.get_with_preferences(user.id)
    if not user_with_prefs:
        raise HTTPException(404, "User not found")
    prefs = [
        TopicPreference(topic=p.topic, weight=p.weight)
        for p in user_with_prefs.preferences
    ]
    return PreferencesResponse(preferences=prefs)


@router.put("/", response_model=PreferencesResponse)
async def update_preferences(
    body: PreferencesUpdate,
    user: CurrentUser,
    repo: Annotated[PreferencesRepository, Depends(get_prefs_repo)],
):
    invalid = {p.topic for p in body.preferences if p.topic not in VALID_TOPICS}
    if invalid:
        raise HTTPException(422, f"Invalid topics: {', '.join(sorted(invalid))}")

    topics = {p.topic: p.weight for p in body.preferences}
    prefs = await repo.set_preferences(user.id, topics)
    return PreferencesResponse(
        preferences=[TopicPreference(topic=p.topic, weight=p.weight) for p in prefs]
    )
