from datetime import datetime

from pydantic import BaseModel

from app.models.source import SourceType


class SourceResponse(BaseModel):
    id: int
    name: str
    url: str
    type: SourceType
    language: str
    country: str | None
    topics: str | None
    is_active: bool
    fetch_interval_minutes: int
    last_fetched_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceCreate(BaseModel):
    name: str
    url: str
    type: SourceType
    language: str = "en"
    country: str | None = None
    topics: str | None = None  # JSON list: ["politics","tech"]


class UserSourceSettingResponse(BaseModel):
    source: SourceResponse
    enabled: bool
    blacklisted: bool

    model_config = {"from_attributes": True}


class UserSourceSettingUpdate(BaseModel):
    enabled: bool | None = None
    blacklisted: bool | None = None
