import base64
import hashlib
import hmac
import time
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


def verify_telegram_hash(data: dict) -> bool:
    received_hash = data.get("hash")
    if not received_hash:
        return False

    # принимаем только свежие данные — не старше 10 минут
    if time.time() - int(data.get("auth_date", 0)) > 600:
        return False

    # все поля кроме hash, отсортированные, каждое на новой строке
    check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items()) if k != "hash"
    )

    # secret_key = SHA256(bot_token) — требование Telegram
    secret_key = hashlib.sha256(settings.telegram_bot_token.encode()).digest()

    # HMAC-SHA256, compare_digest защищает от timing атак
    computed = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, received_hash)
