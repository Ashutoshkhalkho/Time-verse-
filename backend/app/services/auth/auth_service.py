import uuid
from datetime import UTC, datetime

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import (
    RevokedToken,
    User,
)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Validates email and password, returning active user or raising UnauthorizedException."""
    stmt = (
        select(User)
        .options(
            selectinload(User.department_scopes),
            selectinload(User.student_enrollments),
        )
        .where(User.email == email)
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise UnauthorizedException("Invalid email or password.")

    if not user.is_active:
        raise UnauthorizedException("User account has been deactivated.")

    if not verify_password(password, user.hashed_password):
        raise UnauthorizedException("Invalid email or password.")

    return user


async def issue_tokens_for_user(user: User) -> dict:
    """Issues access token and refresh token containing user jurisdiction scopes."""
    dept_ids = [scope.department_id for scope in user.department_scopes]
    section_ids = [enrollment.cohort_section_id for enrollment in user.student_enrollments if enrollment.is_active]

    access_token, access_jti, access_exp = create_access_token(
        subject=user.id,
        role=user.role.value,
        institution_id=user.institution_id,
        department_ids=dept_ids,
        section_ids=section_ids,
    )

    refresh_token, refresh_jti, refresh_exp = create_refresh_token(subject=user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": access_exp.isoformat(),
        "refresh_token": refresh_token,
        "refresh_expires_at": refresh_exp.isoformat(),
    }


async def is_token_revoked(db: AsyncSession, jti: str) -> bool:
    """Checks whether a token JTI has been blacklisted upon logout."""
    stmt = select(RevokedToken).where(RevokedToken.jti == jti)
    result = await db.execute(stmt)
    return result.scalars().first() is not None


async def revoke_token(db: AsyncSession, token_str: str) -> None:
    """Revokes a JWT token by storing its JTI in the revocation ledger."""
    try:
        payload = decode_token(token_str)
        jti = payload.get("jti")
        user_id = payload.get("sub")
        exp_ts = payload.get("exp")
        token_type = payload.get("type", "access")

        if not jti or not user_id or not exp_ts:
            return

        expires_at = datetime.fromtimestamp(exp_ts, tz=UTC)

        revocation = RevokedToken(
            id=f"rev_{uuid.uuid4().hex[:22]}",
            jti=jti,
            token_type=token_type,
            user_id=user_id,
            expires_at=expires_at,
            revoked_at=datetime.now(UTC),
        )
        db.add(revocation)
        await db.flush()
    except (jwt.PyJWTError, Exception):
        # Even if token is already expired or malformed, treat logout as completed
        pass


async def refresh_access_token(db: AsyncSession, refresh_token_str: str) -> dict:
    """Validates refresh token and issues a new access token."""
    try:
        payload = decode_token(refresh_token_str)
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Refresh token has expired. Please sign in again.") from None
    except jwt.PyJWTError:
        raise UnauthorizedException("Invalid refresh token.") from None

    if payload.get("type") != "refresh":
        raise UnauthorizedException("Token provided is not a refresh token.")

    jti = payload.get("jti")
    if jti and await is_token_revoked(db, jti):
        raise UnauthorizedException("Refresh token has been revoked.")

    user_id = payload.get("sub")
    stmt = (
        select(User)
        .options(
            selectinload(User.department_scopes),
            selectinload(User.student_enrollments),
        )
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        raise UnauthorizedException("User account not found or deactivated.")

    dept_ids = [scope.department_id for scope in user.department_scopes]
    section_ids = [enrollment.cohort_section_id for enrollment in user.student_enrollments if enrollment.is_active]

    new_access_token, _, access_exp = create_access_token(
        subject=user.id,
        role=user.role.value,
        institution_id=user.institution_id,
        department_ids=dept_ids,
        section_ids=section_ids,
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_at": access_exp.isoformat(),
    }
