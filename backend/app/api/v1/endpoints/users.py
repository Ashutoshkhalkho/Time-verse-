import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import PermissionGuard, get_current_user
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.permissions import Permission
from app.core.security import get_password_hash
from app.db.session import get_db_session
from app.models.user import (
    StudentEnrollment,
    User,
    UserDepartmentScope,
    UserRoleEnum,
)
from app.schemas.user import (
    UserCreateRequest,
    UserDetailResponse,
    UserUpdateRequest,
)
from app.services.audit.audit_service import record_audit_event

router = APIRouter(prefix="/users", tags=["User Management"])


def serialize_user(user: User) -> UserDetailResponse:
    dept_ids = [scope.department_id for scope in user.department_scopes]
    section_ids = [
        enrollment.cohort_section_id
        for enrollment in user.student_enrollments
        if enrollment.is_active
    ]
    return UserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        institution_id=user.institution_id,
        is_active=user.is_active,
        department_ids=dept_ids,
        section_ids=section_ids,
        created_at=user.created_at.isoformat(),
    )


@router.post(
    "",
    response_model=UserDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision User Account",
    description="Administrators provision new user accounts and assign initial roles and scopes.",
    dependencies=[Depends(PermissionGuard(Permission.USER_CREATE))],
)
async def create_user(
    payload: UserCreateRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserDetailResponse:
    # 1. Check duplicate email
    existing_stmt = select(User).where(User.email == payload.email)
    existing = (await db.execute(existing_stmt)).scalars().first()
    if existing:
        raise ConflictException(f"User with email '{payload.email}' already exists.")

    user_id = f"usr_{uuid.uuid4().hex[:22]}"
    new_user = User(
        id=user_id,
        institution_id=current_user.institution_id,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    # 2. Assign department scopes
    for dept_id in payload.department_ids:
        scope = UserDepartmentScope(
            id=f"uds_{uuid.uuid4().hex[:22]}",
            user_id=user_id,
            department_id=dept_id,
            is_primary=True,
        )
        db.add(scope)

    # 3. Assign section scopes (for students/CRs)
    for sec_id in payload.section_ids:
        enrollment = StudentEnrollment(
            id=f"enr_{uuid.uuid4().hex[:22]}",
            student_user_id=user_id,
            cohort_section_id=sec_id,
            is_active=True,
        )
        db.add(enrollment)

    await db.flush()

    # 4. Record security audit event
    await record_audit_event(
        db=db,
        action="USER_PROVISION",
        resource_type="user",
        resource_id=user_id,
        institution_id=current_user.institution_id,
        actor_user_id=current_user.id,
        after_state={
            "email": payload.email,
            "role": payload.role.value,
            "departments": payload.department_ids,
            "sections": payload.section_ids,
        },
        reason="Administrative user onboarding",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Reload user with relationships
    stmt = (
        select(User)
        .options(
            selectinload(User.department_scopes),
            selectinload(User.student_enrollments),
        )
        .where(User.id == user_id)
    )
    created_user = (await db.execute(stmt)).scalars().one()
    return serialize_user(created_user)


@router.get(
    "",
    response_model=list[UserDetailResponse],
    summary="List Users",
    description="Lists users within the actor's jurisdictional scope.",
)
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[UserDetailResponse]:
    stmt = select(User).options(
        selectinload(User.department_scopes),
        selectinload(User.student_enrollments),
    )

    if current_user.role == UserRoleEnum.ADMIN:
        # Admin views all users in institution
        stmt = stmt.where(User.institution_id == current_user.institution_id)
    elif current_user.role == UserRoleEnum.HOD:
        # HOD views users scoped to their departments
        dept_ids = [scope.department_id for scope in current_user.department_scopes]
        stmt = stmt.join(User.department_scopes).where(
            UserDepartmentScope.department_id.in_(dept_ids)
        )
    else:
        raise ForbiddenException("User lacks permission to query user directory.")

    result = await db.execute(stmt)
    users = result.scalars().unique().all()
    return [serialize_user(u) for u in users]


@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Get User Detail",
)
async def get_user_by_id(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserDetailResponse:
    stmt = (
        select(User)
        .options(
            selectinload(User.department_scopes),
            selectinload(User.student_enrollments),
        )
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    target_user = result.scalars().first()

    if not target_user:
        raise NotFoundException(f"User '{user_id}' not found.")

    # Access control: Admin, Self, or HOD of same department
    if current_user.role == UserRoleEnum.ADMIN or current_user.id == target_user.id:
        return serialize_user(target_user)

    if current_user.role == UserRoleEnum.HOD:
        my_depts = {scope.department_id for scope in current_user.department_scopes}
        their_depts = {scope.department_id for scope in target_user.department_scopes}
        if my_depts.intersection(their_depts):
            return serialize_user(target_user)

    raise ForbiddenException("Access to target user record is forbidden.")


@router.patch(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Update User Role or Status",
    description="Administrative endpoint to update roles, active status, and scopes.",
    dependencies=[Depends(PermissionGuard(Permission.USER_ASSIGN_ROLE))],
)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserDetailResponse:
    stmt = (
        select(User)
        .options(
            selectinload(User.department_scopes),
            selectinload(User.student_enrollments),
        )
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    target_user = result.scalars().first()

    if not target_user:
        raise NotFoundException(f"User '{user_id}' not found.")

    before_state = {
        "role": target_user.role.value,
        "is_active": target_user.is_active,
        "full_name": target_user.full_name,
    }

    if payload.full_name is not None:
        target_user.full_name = payload.full_name
    if payload.phone is not None:
        target_user.phone = payload.phone
    if payload.role is not None:
        target_user.role = payload.role
    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    await db.flush()

    after_state = {
        "role": target_user.role.value,
        "is_active": target_user.is_active,
        "full_name": target_user.full_name,
    }

    await record_audit_event(
        db=db,
        action="USER_UPDATE",
        resource_type="user",
        resource_id=user_id,
        institution_id=current_user.institution_id,
        actor_user_id=current_user.id,
        before_state=before_state,
        after_state=after_state,
        reason="Administrative profile update",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return serialize_user(target_user)
