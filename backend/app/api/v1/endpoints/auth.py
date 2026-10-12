from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_token_from_header
from app.core.permissions import ROLE_PERMISSIONS_MAP
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenResponse,
    UserProfileResponse,
)
from app.services.auth.auth_service import (
    authenticate_user,
    issue_tokens_for_user,
    refresh_access_token,
    revoke_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User Login",
    description="Authenticates credentials and returns access & refresh tokens.",
)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    user = await authenticate_user(db, payload.email, payload.password)
    tokens_dict = await issue_tokens_for_user(user)

    dept_ids = [scope.department_id for scope in user.department_scopes]
    section_ids = [enrollment.cohort_section_id for enrollment in user.student_enrollments if enrollment.is_active]
    perms = [p.value for p in ROLE_PERMISSIONS_MAP.get(user.role, set())]

    user_profile = UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        institution_id=user.institution_id,
        department_ids=dept_ids,
        section_ids=section_ids,
        permissions=perms,
        is_active=user.is_active,
    )

    tokens = TokenResponse(
        access_token=tokens_dict["access_token"],
        token_type=tokens_dict["token_type"],
        expires_at=tokens_dict["expires_at"],
        refresh_token=tokens_dict["refresh_token"],
        refresh_expires_at=tokens_dict["refresh_expires_at"],
    )

    return LoginResponse(tokens=tokens, user=user_profile)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Access Token",
    description="Exchanges a valid refresh token for a new access token.",
)
async def refresh_token(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    new_tokens = await refresh_access_token(db, payload.refresh_token)
    return TokenResponse(
        access_token=new_tokens["access_token"],
        token_type=new_tokens["token_type"],
        expires_at=new_tokens["expires_at"],
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Invalidates the current session by recording token revocation.",
)
async def logout(
    token: Annotated[str, Depends(get_token_from_header)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    await revoke_token(db, token)
    return {"status": "success", "message": "Successfully logged out and session terminated."}


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Current User Profile",
    description="Returns current authenticated user profile, assigned roles, scopes, and permissions.",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserProfileResponse:
    dept_ids = [scope.department_id for scope in current_user.department_scopes]
    section_ids = [enrollment.cohort_section_id for enrollment in current_user.student_enrollments if enrollment.is_active]
    perms = [p.value for p in ROLE_PERMISSIONS_MAP.get(current_user.role, set())]

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        institution_id=current_user.institution_id,
        department_ids=dept_ids,
        section_ids=section_ids,
        permissions=perms,
        is_active=current_user.is_active,
    )
