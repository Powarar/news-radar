import base64
import hashlib
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h
REFRESH_TOKEN_EXPIRE_DAYS = 30


def _prehash(password: str) -> str:
    """SHA-256 pre-hash so bcrypt's 72-byte limit is never hit."""
    digest = hashlib.sha256(password.encode()).digest()
    return base64.b64encode(digest).decode()


def hash_password(password: str) -> str:
    return pwd_context.hash(_prehash(password))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_prehash(plain), hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "access"},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "refresh"},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
