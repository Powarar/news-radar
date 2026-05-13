from datetime import datetime, timezone
import json
import secrets

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_telegram_hash,
    verify_webapp_init_data,
)
from app.core.redis import redis
from app.core.config import settings
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

        hashed = hash_password(data.password)
        user = await self.repo.create(data.email, data.username, hashed)
        return self._make_tokens(user.id)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.repo.get_by_email(data.email)
        if not user or not user.hashed_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not verify_password(data.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
        return self._make_tokens(user.id)

    async def google_login(self, user_info: dict) -> str:
        google_id = user_info["sub"]
        email = user_info["email"]
        name = user_info.get("name", "")

        user = await self.repo.get_by_google_id(google_id)

        if not user:
            user = await self.repo.get_by_email(email)
            if user:
                await self.repo.update(user, {"google_id": google_id})
            else:
                username = name.replace(" ", "_").lower() or email.split("@")[0]
                if await self.repo.get_by_username(username):
                    username = f"{username}_{google_id[:6]}"
                user = await self.repo.create_google(email, username, google_id)

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

        tokens = self._make_tokens(user.id)
        code = secrets.token_hex(32)

        await redis.set(
            f"oauth_code:{code}",
            json.dumps({"access_token": tokens.access_token, "refresh_token": tokens.refresh_token}),
            ex=settings.oauth_code_ttl,
        )

        return code

    async def telegram_webapp_login(self, init_data: str) -> TokenResponse:
        user_data = verify_webapp_init_data(init_data)
        if not user_data:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid WebApp data")

        telegram_id = str(user_data.get("id", ""))
        if not telegram_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user id in WebApp data")

        username = user_data.get("username") or f"tg_{telegram_id}"

        user = await self.repo.get_by_telegram_id(telegram_id)
        if not user:
            if await self.repo.get_by_username(username):
                username = f"{username}_{telegram_id[:6]}"
            user = await self.repo.create_telegram(username, telegram_id)

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

        return self._make_tokens(user.id)

    async def telegram_login(self, data: dict) -> TokenResponse:
        if not verify_telegram_hash(data):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram data")

        telegram_id = str(data["id"])
        username = data.get("username") or f"tg_{telegram_id}"

        user = await self.repo.get_by_telegram_id(telegram_id)

        if not user:
            if await self.repo.get_by_username(username):
                username = f"{username}_{telegram_id[:6]}"
            user = await self.repo.create_telegram(username, telegram_id)

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

        return self._make_tokens(user.id)

    async def telegram_magic_link(self, telegram_id: str) -> str:
        user = await self.repo.get_by_telegram_id(telegram_id)

        if not user:
            username = f"tg_{telegram_id}"
            if await self.repo.get_by_username(username):
                username = f"{username}_{telegram_id[:6]}"
            user = await self.repo.create_telegram(username, telegram_id)

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

        tokens = self._make_tokens(user.id)
        code = secrets.token_hex(32)

        await redis.set(
            f"oauth_code:{code}",
            json.dumps({"access_token": tokens.access_token, "refresh_token": tokens.refresh_token}),
            ex=settings.oauth_code_ttl,
        )

        return code

    async def exchange_oauth_code(self, code: str) -> TokenResponse:
        raw = await redis.get(f"oauth_code:{code}")

        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

        await redis.delete(f"oauth_code:{code}")

        data = json.loads(raw)
        return TokenResponse(**data)

    async def refresh(self, data: RefreshRequest) -> TokenResponse:
        try:
            payload = decode_token(data.refresh_token)
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return self._make_tokens(payload["sub"])

    @staticmethod
    def _make_tokens(user_id: int) -> TokenResponse:
        subject = str(user_id)
        return TokenResponse(
            access_token=create_access_token(subject),
            refresh_token=create_refresh_token(subject),
        )

    async def logout(self, token: str) -> None:
        payload = decode_token(token)
        ttl = payload["exp"] - int(datetime.now(timezone.utc).timestamp())

        if ttl > 0:
            await redis.setex(f"blacklist:{token}", ttl, "1")
        return