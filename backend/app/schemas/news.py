from datetime import datetime

from pydantic import BaseModel

from app.models.news import ReactionType


class NewsItemBrief(BaseModel):
    id: int
    title: str | None
    summary: str | None
    url: str | None
    image_url: str | None
    language: str
    topics: str | None
    importance_score: float
    published_at: datetime | None
    source_id: int

    model_config = {"from_attributes": True}


class NewsItemResponse(NewsItemBrief):
    body: str
    created_at: datetime


class NewsReactionRequest(BaseModel):
    reaction: ReactionType


class NewsReactionResponse(BaseModel):
    id: int
    user_id: int
    news_item_id: int
    reaction: ReactionType
    created_at: datetime

    model_config = {"from_attributes": True}
