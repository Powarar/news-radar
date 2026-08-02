import json
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.redis import redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_telegram_hash,
    verify_webapp_init_data,
)
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def register(self, data: RegisterRequest) -> TokenResponse:
        if await self.repo.get_by_email(data.email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        if await self.repo.get_by_username(data.username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

        # bcrypt is deliberately CPU-expensive; keep it off the API event loop.
        hashed = await run_in_threadpool(hash_password, data.password)
        user = await self.repo.create(data.email, data.username, hashed)
        return self._make_tokens(user.id)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.repo.get_by_email(data.email)
        if not user or not user.hashed_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        password_ok = await run_in_threadpool(
            verify_password,
            data.password,
            user.hashed_password,
        )
        if not password_ok:
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

    async def exchange_oauth_code(self, code: str) -> TokenResponse:
        # GETDEL is atomic: two concurrent exchanges cannot redeem one code twice.
        raw = await redis.getdel(f"oauth_code:{code}")

        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

        data = json.loads(raw)
        return TokenResponse(**data)

    async def refresh(self, data: RefreshRequest) -> TokenResponse:
        try:
            payload = decode_token(data.refresh_token)
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            ) from exc
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        try:
            user_id = int(payload["sub"])
            jti = payload["jti"]
            ttl = payload["exp"] - int(datetime.now(timezone.utc).timestamp())
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            ) from exc

        if ttl <= 0:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

        # Redis SET NX makes each refresh token single-use and rejects replay.
        accepted = await redis.set(f"used_refresh:{jti}", "1", ex=ttl, nx=True)
        if not accepted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token already used",
            )

        user = await self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable")

        return self._make_tokens(user.id)

    @staticmethod
    def _make_tokens(user_id: int) -> TokenResponse:
        subject = str(user_id)
        return TokenResponse(
            access_token=create_access_token(subject),
            refresh_token=create_refresh_token(subject),
        )

    async def logout(self, token: str) -> None:
        try:
            payload = decode_token(token)
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        ttl = payload["exp"] - int(datetime.now(timezone.utc).timestamp())

        if ttl > 0:
            await redis.setex(f"blacklist:{token}", ttl, "1")
