from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def register(self, data: RegisterRequest) -> TokenResponse:
        if await self.repo.get_by_email(data.email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        if await self.repo.get_by_username(data.username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

        hashed = security.hash_password(data.password)
        user = await self.repo.create(data.email, data.username, hashed)
        return self._make_tokens(user.id)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.repo.get_by_email(data.email)
        if not user or not user.hashed_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not security.verify_password(data.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
        return self._make_tokens(user.id)

    async def refresh(self, data: RefreshRequest) -> TokenResponse:
        try:
            payload = security.decode_token(data.refresh_token)
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return self._make_tokens(payload["sub"])

    @staticmethod
    def _make_tokens(user_id: int) -> TokenResponse:
        subject = str(user_id)
        return TokenResponse(
            access_token=security.create_access_token(subject),
            refresh_token=security.create_refresh_token(subject),
        )
