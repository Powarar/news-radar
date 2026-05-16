import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, OptionalUser
from app.repositories.sources import SourcesRepository
from app.schemas.sources import SourceCreateRequest, SourceResponse

router = APIRouter()


def get_sources_repo(db: Annotated[AsyncSession, Depends(get_db)]) -> SourcesRepository:
    return SourcesRepository(db)


@router.get("/")
async def list_sources(
    user: OptionalUser,
    repo: Annotated[SourcesRepository, Depends(get_sources_repo)],
):
    """Все источники. Если пользователь авторизован — с его настройками."""
    if user:
        items = await repo.list_for_user(user.id)
    else:
        items = await repo.list_all()
    return {"items": items}


@router.post("/", response_model=SourceResponse, status_code=201)
async def add_source(
    data: SourceCreateRequest,
    repo: Annotated[SourcesRepository, Depends(get_sources_repo)],
):
    """Добавить новый источник (TG канал или сайт)."""
    try:
        source = await repo.create(data.model_dump())
    except Exception:
        raise HTTPException(400, "Source already exists or invalid data")
    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "type": source.type.value,
        "language": source.language,
        "country": source.country,
        "topics": json.loads(source.topics) if source.topics else None,
        "enabled": True,
        "blacklisted": False,
    }


@router.patch("/{source_id}/toggle")
async def toggle_source(
    source_id: int,
    user: CurrentUser,
    repo: Annotated[SourcesRepository, Depends(get_sources_repo)],
):
    """Включить/выключить источник для текущего пользователя."""
    result = await repo.toggle(user.id, source_id)
    if not result:
        raise HTTPException(404, "Source not found")
    return result


@router.patch("/{source_id}/blacklist")
async def blacklist_source(
    source_id: int,
    user: CurrentUser,
    repo: Annotated[SourcesRepository, Depends(get_sources_repo)],
):
    """Заблокировать источник (скрыть из ленты)."""
    result = await repo.set_blacklist(user.id, source_id, True)
    if not result:
        raise HTTPException(404, "Source not found")
    return result
