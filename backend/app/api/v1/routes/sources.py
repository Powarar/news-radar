import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import AdminUser, CurrentUser, OptionalUser
from app.core.database import get_db
from app.core.rate_limit import RateLimiter
from app.repositories.sources import SourcesRepository
from app.schemas.sources import SourceCreateRequest, SourceResponse

router = APIRouter()
source_create_rate_limit = RateLimiter(max_requests=3, window_seconds=60 * 60)


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
    user: AdminUser,
    _rate_limit: Annotated[None, Depends(source_create_rate_limit)],
):
    """Добавить глобальный источник (только администратор)."""
    try:
        source = await repo.create(data.model_dump())
    except IntegrityError:
        raise HTTPException(409, "Source with this URL already exists")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "type": source.type.value if hasattr(source.type, "value") else source.type,
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
    result = await repo.toggle_blacklist(user.id, source_id)
    if not result:
        raise HTTPException(404, "Source not found")
    return result
