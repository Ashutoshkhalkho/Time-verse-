import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

# Argon2id password hasher
_password_hasher = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against an Argon2id hash."""
    return _password_hasher.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generates an Argon2id password hash."""
    return _password_hasher.hash(password)


def create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    additional_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    """Generates a signed JWT with unique jti identifier and claims."""
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = str(uuid.uuid4())

    claims: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "nbf": int(now.timestamp()),
    }
    if additional_claims:
        claims.update(additional_claims)

    encoded_jwt = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt, jti, expires_at


def create_access_token(
    subject: str,
    role: str,
    institution_id: str,
    department_ids: list[str],
    section_ids: list[str],
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    """Issues an access token containing identity, role, and jurisdiction scopes."""
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    claims = {
        "role": role,
        "institution_id": institution_id,
        "department_ids": department_ids,
        "section_ids": section_ids,
    }
    return create_token(subject, "access", delta, claims)


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> tuple[str, str, datetime]:
    """Issues a long-lived refresh token."""
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(subject, "refresh", delta)


def decode_token(token: str) -> dict[str, Any]:
    """Decodes and validates JWT signature and standard claims."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
