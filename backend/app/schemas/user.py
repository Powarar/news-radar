from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import UserPlan


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    is_active: bool
    plan: UserPlan
    language: str
    country: str | None
    telegram_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: str | None = None
    language: str | None = None
    country: str | None = None
