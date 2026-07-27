from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.news import (
    NewsItemBrief,
    NewsItemResponse,
    NewsReactionRequest,
    NewsReactionResponse,
)
from app.schemas.preferences import (
    PreferencesResponse,
    PreferencesUpdate,
    TopicPreference,
)
from app.schemas.source import (
    SourceCreate,
    SourceResponse,
    UserSourceSettingResponse,
    UserSourceSettingUpdate,
)
from app.schemas.user import UserResponse, UserUpdate

__all__ = [
    "LoginRequest",
    "NewsItemBrief",
    "NewsItemResponse",
    "NewsReactionRequest",
    "NewsReactionResponse",
    "PreferencesResponse",
    "PreferencesUpdate",
    "RefreshRequest",
    "RegisterRequest",
    "SourceCreate",
    "SourceResponse",
    "TokenResponse",
    "TopicPreference",
    "UserResponse",
    "UserSourceSettingResponse",
    "UserSourceSettingUpdate",
    "UserUpdate",
]
