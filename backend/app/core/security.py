from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
import jwt as pyjwt
from pydantic import BaseModel

from app.core.config import settings

_ph = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return _ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against an Argon2id hash. Never raises."""
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(
        payload, settings.jwt_secret, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> Optional[str]:
    """Decode a signed JWT; return subject or None for invalid/expired."""
    try:
        payload = pyjwt.decode(
            token, settings.jwt_secret, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload.get("sub")
    except Exception:
        return None
