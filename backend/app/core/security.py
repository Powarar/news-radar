import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h
REFRESH_TOKEN_EXPIRE_DAYS = 30


def _prehash(password: str) -> str:
    """SHA-256 pre-hash so bcrypt's 72-byte limit is never hit."""
    digest = hashlib.sha256(password.encode()).digest()
    return base64.b64encode(digest).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password).encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prehash(plain).encode(), hashed.encode())


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": subject, "exp": expire, "jti": secrets.token_hex(8), "type": "access"},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": subject, "exp": expire, "jti": secrets.token_hex(8), "type": "refresh"},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def _is_recent_auth_date(raw_auth_date: object, *, max_age_seconds: int = 600) -> bool:
    try:
        auth_date = int(raw_auth_date)
    except (TypeError, ValueError):
        return False
    age = time.time() - auth_date
    return 0 <= age <= max_age_seconds


def verify_webapp_init_data(init_data: str) -> dict | None:
    """Verify Telegram Mini App initData and return parsed user dict, or None if invalid."""
    import json
    from urllib.parse import parse_qsl

    params = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        return None

    if not _is_recent_auth_date(params.get("auth_date")):
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

    # Mini App key derivation differs from Login Widget: HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return None

    try:
        return json.loads(params.get("user", "{}"))
    except (json.JSONDecodeError, TypeError):
        return None


def verify_telegram_hash(data: dict) -> bool:
    received_hash = data.get("hash")
    if not received_hash:
        return False

    if not _is_recent_auth_date(data.get("auth_date")):
        return False

    check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items()) if k != "hash"
    )

    # secret_key = SHA256(bot_token) — требование Telegram
    secret_key = hashlib.sha256(settings.telegram_bot_token.encode()).digest()

    # HMAC-SHA256, compare_digest защищает от timing атак
    computed = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, received_hash)
