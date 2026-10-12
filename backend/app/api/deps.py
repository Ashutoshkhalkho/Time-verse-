from typing import Annotated

import jwt
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.permissions import ROLE_PERMISSIONS_MAP, Permission
from app.core.security import decode_token
from app.db.session import get_db_session
from app.models.user import User, UserRoleEnum
from app.services.auth.auth_service import is_token_revoked


async def get_token_from_header(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extracts raw JWT Bearer token from the HTTP Authorization header."""
    if not authorization:
        raise UnauthorizedException("Missing Authorization header with Bearer token.")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedException("Invalid Authorization format. Expected: 'Bearer <token>'.")

    return parts[1]


async def get_current_user(
    token: Annotated[str, Depends(get_token_from_header)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Validates JWT access token, checks revocation ledger, and returns the active user."""
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Access token has expired. Please refresh your session.") from None
    except jwt.PyJWTError:
        raise UnauthorizedException("Invalid access token.") from None

    if payload.get("type") != "access":
        raise UnauthorizedException("Supplied token is not an access token.")

    jti = payload.get("jti")
    if jti and await is_token_revoked(db, jti):
        raise UnauthorizedException("Session has been terminated. Please log in again.")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Access token payload missing user identifier.")

    stmt = (
        select(User)
        .options(
            selectinload(User.department_scopes),
            selectinload(User.student_enrollments),
            selectinload(User.mentee_assignments),
        )
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise UnauthorizedException("User account associated with this token no longer exists.")

    if not user.is_active:
        raise UnauthorizedException("User account has been deactivated.")

    return user


class PermissionGuard:
    """Server-side authorization guard enforcing RBAC and resource scoping boundaries."""

    def __init__(
        self,
        permission: Permission,
        require_department_scope: bool = False,
        require_section_scope: bool = False,
    ):
        self.permission = permission
        self.require_department_scope = require_department_scope
        self.require_section_scope = require_section_scope

    async def __call__(
        self,
        current_user: Annotated[User, Depends(get_current_user)],
        department_id: str | None = None,
        section_id: str | None = None,
    ) -> User:
        # 1. Global Admin bypass for institution-wide administrative authority
        if current_user.role == UserRoleEnum.ADMIN:
            return current_user

        # 2. Verify Role-Permission mapping
        allowed_perms = ROLE_PERMISSIONS_MAP.get(current_user.role, set())
        if self.permission not in allowed_perms:
            raise ForbiddenException(
                f"Role '{current_user.role.value}' lacks permission '{self.permission}' for this operation."
            )

        # 3. Verify Department Jurisdiction (HOD, Coordinator, Teacher)
        if self.require_department_scope and department_id:
            user_depts = [scope.department_id for scope in current_user.department_scopes]
            if department_id not in user_depts:
                raise ForbiddenException(
                    f"User not authorized for department '{department_id}'."
                )

        # 4. Verify Section/Cohort Jurisdiction (CR, Student)
        if self.require_section_scope and section_id:
            user_sections = [
                enrollment.cohort_section_id
                for enrollment in current_user.student_enrollments
                if enrollment.is_active
            ]
            if section_id not in user_sections:
                raise ForbiddenException(
                    f"User not authorized for section '{section_id}'."
                )

        return current_user
