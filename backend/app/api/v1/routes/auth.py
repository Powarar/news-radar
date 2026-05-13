from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

from app.core.database import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, OAuthCodeRequest
from app.services.auth import AuthService
from app.core.config import settings
from app.api.v1.deps import bearer


router = APIRouter()

config = Config(environ={
    "GOOGLE_CLIENT_ID": settings.google_client_id,
    "GOOGLE_CLIENT_SECRET": settings.google_client_secret,
})

oauth = OAuth(config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def get_auth_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(db)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    data: RegisterRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    return await service.register(data)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    return await service.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    return await service.refresh(data)


@router.get("/google/login")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/google/callback", name="google_callback")
async def google_callback(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")

    code = await service.google_login(user_info)

    return RedirectResponse(f"{settings.frontend_url}/oauth/callback?code={code}")


@router.post("/telegram/webapp", response_model=TokenResponse)
async def telegram_webapp_login(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    data = await request.json()
    return await service.telegram_webapp_login(data.get("init_data", ""))


@router.post("/telegram", response_model=TokenResponse)
async def telegram_login(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    data = await request.json()
    return await service.telegram_login(data)


@router.post("/telegram/magic-link")
async def telegram_magic_link(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    bot_token = request.headers.get("X-Bot-Token", "")
    if not settings.telegram_bot_token or bot_token != settings.telegram_bot_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bot token")

    data = await request.json()
    telegram_id = str(data.get("telegram_id", ""))
    if not telegram_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="telegram_id required")

    code = await service.telegram_magic_link(telegram_id)
    return {"code": code}


@router.post("/exchange", response_model=TokenResponse)
async def exchange_oauth_code(
    data: OAuthCodeRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    return await service.exchange_oauth_code(data.code)


@router.post("/logout", status_code=204)
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)]
):
    return await service.logout(credentials.credentials)
    
