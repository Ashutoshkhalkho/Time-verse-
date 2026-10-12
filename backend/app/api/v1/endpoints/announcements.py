import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.db.session import get_db_session
from app.models.alert import Alert, AlertSeverityEnum
from app.models.announcement import (
    Announcement,
    AnnouncementCategoryEnum,
    AnnouncementTargetAudienceEnum,
)
from app.models.audit import AuditEvent
from app.models.user import StudentEnrollment, User, UserDepartmentScope, UserRoleEnum

router = APIRouter(prefix="/announcements", tags=["Announcements"])


def generate_ulid() -> str:
    return uuid.uuid4().hex[:26]


class AnnouncementResponse(BaseModel):
    id: str
    title: str
    content: str
    category: AnnouncementCategoryEnum
    severity: AlertSeverityEnum
    target_audience: AnnouncementTargetAudienceEnum
    department_id: str | None = None
    author_user_id: str
    author_name: str
    is_published: bool
    is_pinned: bool
    published_at: datetime
    created_at: datetime
    metadata_json: dict[str, Any] | None = None


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=5)
    category: AnnouncementCategoryEnum = AnnouncementCategoryEnum.ACADEMIC_NOTICE
    severity: AlertSeverityEnum = AlertSeverityEnum.INFORMATIONAL
    target_audience: AnnouncementTargetAudienceEnum = AnnouncementTargetAudienceEnum.ALL
    department_id: str | None = None
    is_pinned: bool = False
    broadcast_as_alert: bool = True


class AnnouncementUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category: AnnouncementCategoryEnum | None = None
    severity: AlertSeverityEnum | None = None
    target_audience: AnnouncementTargetAudienceEnum | None = None
    department_id: str | None = None
    is_published: bool | None = None
    is_pinned: bool | None = None


@router.get("", response_model=list[AnnouncementResponse])
async def list_announcements(
    category: AnnouncementCategoryEnum | None = Query(default=None),
    department_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> list[AnnouncementResponse]:
    """
    Returns published announcements visible to the current user's role and department.
    Pinned announcements are ordered first, followed by publication date descending.
    """
    stmt = (
        select(Announcement)
        .options(selectinload(Announcement.author))
        .where(Announcement.is_published.is_(True))
    )

    # Role-based visibility filtering
    if current_user and current_user.role != UserRoleEnum.ADMIN:
        user_depts = [s.department_id for s in current_user.department_scopes]
        if current_user.role == UserRoleEnum.STUDENT:
            stmt = stmt.where(
                Announcement.target_audience.in_([
                    AnnouncementTargetAudienceEnum.ALL,
                    AnnouncementTargetAudienceEnum.STUDENTS,
                ])
            )
        elif current_user.role in {UserRoleEnum.TEACHER, UserRoleEnum.COORDINATOR, UserRoleEnum.HOD}:
            stmt = stmt.where(
                Announcement.target_audience.in_([
                    AnnouncementTargetAudienceEnum.ALL,
                    AnnouncementTargetAudienceEnum.FACULTY,
                ])
            )

        if user_depts:
            stmt = stmt.where(
                (Announcement.department_id.is_(None)) | (Announcement.department_id.in_(user_depts))
            )
        else:
            stmt = stmt.where(Announcement.department_id.is_(None))

    if category:
        stmt = stmt.where(Announcement.category == category)
    if department_id:
        stmt = stmt.where(Announcement.department_id == department_id)

    stmt = stmt.order_by(desc(Announcement.is_pinned), desc(Announcement.published_at)).limit(limit)

    results = (await db.execute(stmt)).scalars().all()

    return [
        AnnouncementResponse(
            id=a.id,
            title=a.title,
            content=a.content,
            category=a.category,
            severity=a.severity,
            target_audience=a.target_audience,
            department_id=a.department_id,
            author_user_id=a.author_user_id,
            author_name=a.author.full_name if a.author else "Institutional Administration",
            is_published=a.is_published,
            is_pinned=a.is_pinned,
            published_at=a.published_at,
            created_at=a.created_at,
            metadata_json=a.metadata_json,
        )
        for a in results
    ]


@router.get("/admin", response_model=list[AnnouncementResponse])
async def list_admin_announcements(
    limit: int = Query(default=100, ge=1, le=200),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> list[AnnouncementResponse]:
    """Admin view: returns all announcements including drafts and unpublished items."""
    if current_user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
        raise ForbiddenException("Administrator privileges required.")

    stmt = (
        select(Announcement)
        .options(selectinload(Announcement.author))
        .order_by(desc(Announcement.is_pinned), desc(Announcement.created_at))
        .limit(limit)
    )
    results = (await db.execute(stmt)).scalars().all()

    return [
        AnnouncementResponse(
            id=a.id,
            title=a.title,
            content=a.content,
            category=a.category,
            severity=a.severity,
            target_audience=a.target_audience,
            department_id=a.department_id,
            author_user_id=a.author_user_id,
            author_name=a.author.full_name if a.author else "Institutional Administration",
            is_published=a.is_published,
            is_pinned=a.is_pinned,
            published_at=a.published_at,
            created_at=a.created_at,
            metadata_json=a.metadata_json,
        )
        for a in results
    ]


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    payload: AnnouncementCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> AnnouncementResponse:
    """
    Creates and publishes an announcement. Authorized for ADMIN, HOD, and COORDINATOR.
    Optionally dispatches targeted Alert notifications to affected recipients.
    """
    if current_user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
        raise ForbiddenException("Only administrators, HODs, or coordinators may publish announcements.")

    now = datetime.now(UTC)
    announcement_id = generate_ulid()

    announcement = Announcement(
        id=announcement_id,
        title=payload.title,
        content=payload.content,
        category=payload.category,
        severity=payload.severity,
        target_audience=payload.target_audience,
        department_id=payload.department_id,
        author_user_id=current_user.id,
        is_published=True,
        is_pinned=payload.is_pinned,
        published_at=now,
    )
    db.add(announcement)

    # If broadcast_as_alert is True, create alert notifications for relevant users
    if payload.broadcast_as_alert:
        target_users_stmt = select(User.id).where(User.is_active.is_(True))
        if payload.department_id:
            dept_users_stmt = select(UserDepartmentScope.user_id).where(
                UserDepartmentScope.department_id == payload.department_id
            )
            target_uids = (await db.execute(dept_users_stmt)).scalars().all()
            target_users_stmt = target_users_stmt.where(User.id.in_(target_uids))

        if payload.target_audience == AnnouncementTargetAudienceEnum.STUDENTS:
            target_users_stmt = target_users_stmt.where(
                User.role.in_([UserRoleEnum.STUDENT, UserRoleEnum.CR])
            )
        elif payload.target_audience == AnnouncementTargetAudienceEnum.FACULTY:
            target_users_stmt = target_users_stmt.where(
                User.role.in_([UserRoleEnum.TEACHER, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR, UserRoleEnum.MENTOR])
            )

        target_uids = (await db.execute(target_users_stmt)).scalars().all()

        for uid in target_uids:
            alert = Alert(
                id=generate_ulid(),
                recipient_user_id=uid,
                event_type=payload.category.value,
                title=payload.title,
                message=payload.content[:300] + ("..." if len(payload.content) > 300 else ""),
                severity=payload.severity,
                is_read=False,
                metadata_json={
                    "announcement_id": announcement_id,
                    "author_id": current_user.id,
                    "author_name": current_user.full_name,
                },
            )
            db.add(alert)

    # Audit logging
    db.add(
        AuditEvent(
            id=generate_ulid(),
            institution_id=current_user.institution_id or "inst_01",
            actor_user_id=current_user.id,
            action="ANNOUNCEMENT_PUBLISHED",
            resource_type="ANNOUNCEMENT",
            resource_id=announcement_id,
            before_state={},
            after_state={"title": payload.title, "category": payload.category.value},
        )
    )

    await db.commit()
    await db.refresh(announcement)

    return AnnouncementResponse(
        id=announcement.id,
        title=announcement.title,
        content=announcement.content,
        category=announcement.category,
        severity=announcement.severity,
        target_audience=announcement.target_audience,
        department_id=announcement.department_id,
        author_user_id=announcement.author_user_id,
        author_name=current_user.full_name,
        is_published=announcement.is_published,
        is_pinned=announcement.is_pinned,
        published_at=announcement.published_at,
        created_at=announcement.created_at,
        metadata_json=announcement.metadata_json,
    )


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: str,
    payload: AnnouncementUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> AnnouncementResponse:
    """Updates an existing announcement. Requires ADMIN or the original author."""
    stmt = (
        select(Announcement)
        .options(selectinload(Announcement.author))
        .where(Announcement.id == announcement_id)
    )
    announcement = (await db.execute(stmt)).scalars().first()
    if not announcement:
        raise NotFoundException(f"Announcement '{announcement_id}' not found.")

    if current_user.role != UserRoleEnum.ADMIN and announcement.author_user_id != current_user.id:
        raise ForbiddenException("Permission denied to edit this announcement.")

    if payload.title is not None:
        announcement.title = payload.title
    if payload.content is not None:
        announcement.content = payload.content
    if payload.category is not None:
        announcement.category = payload.category
    if payload.severity is not None:
        announcement.severity = payload.severity
    if payload.target_audience is not None:
        announcement.target_audience = payload.target_audience
    if payload.department_id is not None:
        announcement.department_id = payload.department_id
    if payload.is_published is not None:
        announcement.is_published = payload.is_published
    if payload.is_pinned is not None:
        announcement.is_pinned = payload.is_pinned

    await db.commit()
    await db.refresh(announcement)

    return AnnouncementResponse(
        id=announcement.id,
        title=announcement.title,
        content=announcement.content,
        category=announcement.category,
        severity=announcement.severity,
        target_audience=announcement.target_audience,
        department_id=announcement.department_id,
        author_user_id=announcement.author_user_id,
        author_name=announcement.author.full_name if announcement.author else "Administrator",
        is_published=announcement.is_published,
        is_pinned=announcement.is_pinned,
        published_at=announcement.published_at,
        created_at=announcement.created_at,
        metadata_json=announcement.metadata_json,
    )


@router.delete("/{announcement_id}", status_code=status.HTTP_200_OK)
async def delete_announcement(
    announcement_id: str,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict[str, Any]:
    """Deletes an announcement. Requires ADMIN or author."""
    stmt = select(Announcement).where(Announcement.id == announcement_id)
    announcement = (await db.execute(stmt)).scalars().first()
    if not announcement:
        raise NotFoundException(f"Announcement '{announcement_id}' not found.")

    if current_user.role != UserRoleEnum.ADMIN and announcement.author_user_id != current_user.id:
        raise ForbiddenException("Permission denied to delete this announcement.")

    await db.delete(announcement)
    await db.commit()

    return {"message": "Announcement removed successfully.", "id": announcement_id}
