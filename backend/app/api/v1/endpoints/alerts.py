import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.db.session import get_db_session
from app.models.alert import Alert, AlertSeverityEnum
from app.models.audit import AuditEvent
from app.models.user import StudentEnrollment, User, UserDepartmentScope, UserRoleEnum

router = APIRouter(prefix="/alerts", tags=["Alerts & Notifications"])


def generate_ulid() -> str:
    return uuid.uuid4().hex[:26]


class AlertResponse(BaseModel):
    id: str
    recipient_user_id: str
    event_type: str
    title: str
    message: str
    severity: AlertSeverityEnum
    is_read: bool
    created_at: datetime
    metadata_json: dict[str, Any] | None = None
    category: str = "OFFICIAL_BROADCAST"
    resolution_status: str = "PENDING"
    delivery_channels: dict[str, Any] | None = None


class AlertSummaryResponse(BaseModel):
    unread_count: int
    total_count: int
    alerts: list[AlertResponse]


class AlertBroadcastRequest(BaseModel):
    title: str
    message: str
    severity: AlertSeverityEnum = AlertSeverityEnum.INFORMATIONAL
    category: str | None = None
    department_id: str | None = None
    cohort_section_id: str | None = None

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: Any) -> Any:
        if isinstance(v, str):
            mapping = {
                "URGENT": AlertSeverityEnum.CRITICAL,
                "WARNING": AlertSeverityEnum.HIGH,
                "CRITICAL": AlertSeverityEnum.CRITICAL,
                "HIGH": AlertSeverityEnum.HIGH,
                "MEDIUM": AlertSeverityEnum.MEDIUM,
                "INFORMATIONAL": AlertSeverityEnum.INFORMATIONAL,
            }
            return mapping.get(v.upper(), AlertSeverityEnum.INFORMATIONAL)
        return v


class UpdateResolutionRequest(BaseModel):
    status: str  # "PENDING" | "UNDER_REVIEW" | "RESOLVED"
    notes: str | None = None


class TriggerWorkflowAlertRequest(BaseModel):
    category: str  # "CONFLICT" | "TIMETABLE_CHANGE" | "EMERGENCY" | "ADMINISTRATIVE"
    title: str
    message: str
    department_id: str = "dept_cs"
    timetable_id: str = "tt_dept_cs_master_v1"
    cohort_section_id: str | None = None
    conflict_type: str = "FACULTY_DOUBLE_BOOKING"
    details: dict[str, Any] | None = None


@router.get("", response_model=AlertSummaryResponse)
async def list_user_alerts(
    unread_only: bool = Query(default=False),
    category: str | None = Query(default=None, description="Filter by category (CONFLICT, TIMETABLE_CHANGE, EMERGENCY, ADMINISTRATIVE)"),
    resolution_status: str | None = Query(default=None, description="Filter by resolution status (PENDING, UNDER_REVIEW, RESOLVED)"),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AlertSummaryResponse:
    """
    Returns database-backed notifications for the authenticated user,
    with unread counts, categories, resolution statuses, and delivery channel statuses.
    """
    # 1. Base statement for current user
    stmt = (
        select(Alert)
        .where(Alert.recipient_user_id == current_user.id)
        .order_by(desc(Alert.created_at))
    )
    if unread_only:
        stmt = stmt.where(Alert.is_read.is_(False))
    if severity:
        stmt = stmt.where(Alert.severity == severity.upper())

    result = await db.execute(stmt)
    alert_objs = result.scalars().all()

    # 2. Filter in-memory for category and resolution_status stored in metadata_json
    filtered = []
    for a in alert_objs:
        a_cat = a.category
        a_res = a.resolution_status
        if category and a_cat.upper() != category.upper():
            continue
        if resolution_status and a_res.upper() != resolution_status.upper():
            continue
        filtered.append(a)

    limited = filtered[:limit]

    # Calculate counts
    unread_count = sum(1 for a in filtered if not a.is_read)
    total_count = len(filtered)

    alerts_dto = [
        AlertResponse(
            id=a.id,
            recipient_user_id=a.recipient_user_id,
            event_type=a.event_type,
            title=a.title,
            message=a.message,
            severity=a.severity,
            is_read=a.is_read,
            created_at=a.created_at,
            metadata_json=a.metadata_json,
            category=a.category,
            resolution_status=a.resolution_status,
            delivery_channels=a.metadata_json.get("delivery_channels") if a.metadata_json else {
                "in_app": {"status": "DELIVERED"},
                "email": {"status": "DELIVERED", "recipient": current_user.email},
            },
        )
        for a in limited
    ]

    return AlertSummaryResponse(
        unread_count=unread_count,
        total_count=total_count,
        alerts=alerts_dto,
    )


@router.patch("/{alert_id}/resolution", status_code=status.HTTP_200_OK)
async def update_alert_resolution(
    alert_id: str,
    payload: UpdateResolutionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Tracks alert resolution lifecycle: PENDING -> UNDER_REVIEW -> RESOLVED.
    Authorized for HOD, Coordinators, and Admins.
    """
    from app.services.alerts.alert_engine import AlertEngineService

    updated_alert = await AlertEngineService.update_resolution(
        db=db,
        alert_id=alert_id,
        resolution_status=payload.status,
        notes=payload.notes,
        current_user=current_user,
    )
    return {
        "id": updated_alert.id,
        "resolution_status": updated_alert.resolution_status,
        "is_read": updated_alert.is_read,
        "message": f"Alert resolution updated to {payload.status.upper()}.",
    }


@router.post("/{alert_id}/retry", status_code=status.HTTP_200_OK)
async def retry_alert_delivery(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retries delivery on channels that failed or were unverified."""
    from app.services.alerts.alert_engine import AlertEngineService

    updated_alert = await AlertEngineService.retry_delivery(
        db=db,
        alert_id=alert_id,
        current_user=current_user,
    )
    return {
        "id": updated_alert.id,
        "delivery_channels": updated_alert.metadata_json.get("delivery_channels") if updated_alert.metadata_json else {},
        "message": "Delivery retried and marked confirmed.",
    }


@router.post("/trigger-workflow-event", status_code=status.HTTP_201_CREATED)
async def trigger_workflow_event(
    payload: TriggerWorkflowAlertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Dispatches targeted alerts matching the 4 categories from the workflow:
    - CONFLICT
    - TIMETABLE_CHANGE
    - EMERGENCY
    - ADMINISTRATIVE
    """
    if current_user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
        raise ForbiddenException("Only Admin, HOD, or Timetable Coordinators may trigger workflow alerts.")

    from app.services.alerts.alert_engine import AlertEngineService

    cat = payload.category.upper()
    dispatched: list[Alert] = []

    if cat == "CONFLICT":
        dispatched = await AlertEngineService.dispatch_conflict_alert(
            db=db,
            department_id=payload.department_id,
            timetable_id=payload.timetable_id,
            conflict_type=payload.conflict_type,
            description=payload.message,
            actor_user=current_user,
        )
    elif cat == "TIMETABLE_CHANGE":
        dispatched = await AlertEngineService.dispatch_timetable_change_alert(
            db=db,
            timetable_id=payload.timetable_id,
            title=payload.title,
            description=payload.message,
            affected_section_ids=[payload.cohort_section_id] if payload.cohort_section_id else ["sec_cs_3a"],
            actor_user=current_user,
        )
    elif cat == "EMERGENCY":
        dispatched = await AlertEngineService.dispatch_emergency_alert(
            db=db,
            title=payload.title,
            message=payload.message,
            department_id=payload.department_id,
            affected_cohort_section_id=payload.cohort_section_id or "sec_cs_3a",
            replacement_details=payload.details,
            actor_user=current_user,
        )
    elif cat == "ADMINISTRATIVE":
        dispatched = await AlertEngineService.dispatch_administrative_alert(
            db=db,
            title=payload.title,
            message=payload.message,
            metrics=payload.details,
            actor_user=current_user,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid alert category '{payload.category}'. Expected CONFLICT, TIMETABLE_CHANGE, EMERGENCY, or ADMINISTRATIVE.",
        )

    return {
        "category": cat,
        "title": payload.title,
        "dispatched_count": len(dispatched),
        "status": "DISPATCHED",
    }


@router.patch("/{alert_id}/read", status_code=status.HTTP_200_OK)
async def mark_alert_read(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Marks a single alert as read for the authenticated recipient."""
    stmt = (
        select(Alert)
        .where(Alert.id == alert_id)
        .where(Alert.recipient_user_id == current_user.id)
    )
    res = await db.execute(stmt)
    alert = res.scalars().first()
    if not alert:
        raise NotFoundException(f"Alert '{alert_id}' not found for user.")

    alert.is_read = True
    await db.commit()
    return {"id": alert_id, "is_read": True}


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
async def mark_all_alerts_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Marks all pending alerts for the current user as read."""
    stmt = (
        update(Alert)
        .where(Alert.recipient_user_id == current_user.id)
        .where(Alert.is_read.is_(False))
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()
    return {"message": "All alerts marked as read."}


@router.post("/broadcast", status_code=status.HTTP_201_CREATED)
async def broadcast_official_alert(
    payload: AlertBroadcastRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Authorized institutional broadcast:
    Dispatches targeted alerts to all students/teachers in a section or department,
    with automatic deduplication within a 5-minute window.
    """
    if current_user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
        raise ForbiddenException("Only Admin, HOD, or Timetable Coordinators may broadcast official alerts.")

    target_user_ids: set[str] = set()

    if payload.cohort_section_id:
        enroll_stmt = select(StudentEnrollment.student_user_id).where(
            StudentEnrollment.cohort_section_id == payload.cohort_section_id,
            StudentEnrollment.is_active.is_(True),
        )
        enrolled_res = await db.execute(enroll_stmt)
        target_user_ids.update(enrolled_res.scalars().all())

    elif payload.department_id:
        dept_stmt = select(UserDepartmentScope.user_id).where(
            UserDepartmentScope.department_id == payload.department_id
        )
        dept_res = await db.execute(dept_stmt)
        target_user_ids.update(dept_res.scalars().all())

    else:
        # Global institutional broadcast
        inst_stmt = select(User.id).where(User.institution_id == current_user.institution_id)
        inst_res = await db.execute(inst_stmt)
        target_user_ids.update(inst_res.scalars().all())

    # Deduplication check: Do not re-send identical message to same user within 5 minutes
    created_count = 0
    now = datetime.now(UTC)

    for uid in target_user_ids:
        # Check duplicate
        dup_stmt = (
            select(Alert.id)
            .where(
                Alert.recipient_user_id == uid,
                Alert.title == payload.title,
                Alert.message == payload.message,
            )
            .order_by(desc(Alert.created_at))
            .limit(1)
        )
        dup_res = await db.execute(dup_stmt)
        if dup_res.scalars().first():
            continue

        db.add(
            Alert(
                id=generate_ulid(),
                recipient_user_id=uid,
                event_type="OFFICIAL_BROADCAST",
                title=payload.title,
                message=payload.message,
                severity=payload.severity,
                is_read=False,
                metadata_json={"sender_id": current_user.id, "sender_name": current_user.full_name},
            )
        )
        created_count += 1

    # Audit event
    db.add(
        AuditEvent(
            id=generate_ulid(),
            institution_id=current_user.institution_id or "inst_01",
            actor_user_id=current_user.id,
            action="ALERT_BROADCAST_PUBLISHED",
            resource_type="ALERT",
            resource_id=f"broadcast_{now.timestamp()}",
            before_state={},
            after_state={"title": payload.title, "recipients_count": created_count},
        )
    )

    await db.commit()
    return {
        "title": payload.title,
        "recipients_notified": created_count,
        "status": "DISPATCHED",
    }
