from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(user_id: int) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.access_token_expire_minutes * 60
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    token = jwt.encode(
        {"sub": str(user_id), "exp": expires_at, "iat": datetime.now(timezone.utc)},
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )
    return token, expires_in
