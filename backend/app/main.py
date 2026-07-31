import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.routes import auth, bot, news, preferences, sources, users
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="News Radar API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

Instrumentator().instrument(app).expose(app, endpoint="/api/metrics")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=not settings.debug,
    same_site="lax",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(news.router, prefix="/api/v1/news", tags=["news"])
app.include_router(sources.router, prefix="/api/v1/sources", tags=["sources"])
app.include_router(preferences.router, prefix="/api/v1/preferences", tags=["preferences"])
app.include_router(bot.router, prefix="/api/bot", tags=["bot"])


@app.exception_handler(LookupError)
async def lookup_error_handler(request: Request, exc: LookupError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/health/ready")
async def readiness():
    """Report readiness only when PostgreSQL and Redis are reachable."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        await redis.ping()
    except Exception:  # noqa: BLE001 — return a stable readiness response
        logging.exception("Readiness check failed")
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}
