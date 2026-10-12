from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import PermissionGuard, get_current_user
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.permissions import Permission
from app.db.session import get_db_session
from app.models.audit import AuditEvent
from app.models.timetable import SessionStatusEnum, TimetableSession
from app.models.user import User, UserRoleEnum
from app.services.alerts.alert_engine import AlertEngineService
from app.services.scheduler.conflict_service import ConflictService
from app.api.v1.endpoints.scheduling import detect_session_conflicts
from app.services.simulator.schemas import SimulationReport, SimulationScenarioRequest
from app.services.simulator.simulator_service import ImpactSimulator

router = APIRouter(prefix="/simulator", tags=["What-If Impact Simulator"])


class ApplySimulationRequest(BaseModel):
    timetable_id: str
    target_session_id: str
    proposed_time_slot_id: str
    proposed_room_id: str | None = None
    proposed_teacher_id: str | None = None
    reason: str = "Applied simulated schedule modification"


@router.post(
    "/simulate",
    response_model=SimulationReport,
    summary="Run What-If Impact Simulation Sandbox",
    dependencies=[Depends(PermissionGuard(Permission.SIMULATOR_RUN))],
)
async def run_simulation(
    request: SimulationScenarioRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SimulationReport:
    """
    Simulates proposed schedule disruptions or changes in an isolated in-memory sandbox.
    Guarantees ZERO database modifications.
    Identifies directly and indirectly affected sessions and generates ranked alternatives.
    """
    return await ImpactSimulator.simulate(request, db)


@router.post(
    "/apply",
    summary="Apply Simulated Schedule Changes with Preflight Conflict Check and Ripple Alerts",
    dependencies=[Depends(PermissionGuard(Permission.SIMULATOR_RUN))],
)
async def apply_simulated_change(
    payload: ApplySimulationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    Applies an authorized simulated timetable change directly to the database:
    1. Validates user authority (HOD, Coordinator, Admin only).
    2. Protects locked sessions from unauthorized mutation.
    3. Re-validates preflight conflicts against all hard constraints.
    4. Updates database state and records audit event.
    5. Dispatches smart ripple change alerts to affected teachers, students, and CRs.
    6. Re-evaluates post-application timetable conflict status.
    """
    if current_user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
        raise ForbiddenException("Only HOD, Timetable Coordinators, or Administrators may apply simulated schedule adjustments.")

    sess_stmt = (
        select(TimetableSession)
        .options(
            selectinload(TimetableSession.subject),
            selectinload(TimetableSession.teacher),
            selectinload(TimetableSession.room),
            selectinload(TimetableSession.cohort_section),
            selectinload(TimetableSession.time_slot),
        )
        .where(
            TimetableSession.id == payload.target_session_id,
            TimetableSession.timetable_id == payload.timetable_id,
        )
    )
    sess_res = await db.execute(sess_stmt)
    sess = sess_res.scalars().first()
    if not sess:
        raise NotFoundException(f"Session '{payload.target_session_id}' not found in timetable '{payload.timetable_id}'.")

    if sess.is_locked:
        raise ConflictException(detail="Target session is locked by administrative approval. Please unlock prior to applying changes.")

    target_room = payload.proposed_room_id or sess.room_id
    target_teacher = payload.proposed_teacher_id or sess.teacher_id

    # Preflight conflict detection
    conflicts, warnings = await detect_session_conflicts(
        db=db,
        timetable_id=payload.timetable_id,
        time_slot_id=payload.proposed_time_slot_id,
        teacher_id=target_teacher,
        room_id=target_room,
        cohort_section_id=sess.cohort_section_id,
        exclude_session_id=sess.id,
    )
    if conflicts:
        raise ConflictException(detail="; ".join(conflicts))

    # Apply changes
    old_time_slot = sess.time_slot_id
    old_room = sess.room_id
    old_teacher = sess.teacher_id

    sess.time_slot_id = payload.proposed_time_slot_id
    sess.room_id = target_room
    sess.teacher_id = target_teacher
    sess.status = SessionStatusEnum.RESCHEDULED

    # Audit
    db.add(
        AuditEvent(
            id=f"audit_{int(db.bind.dialect.name == 'sqlite')}_{sess.id[:10]}",
            institution_id=current_user.institution_id or "inst_01",
            actor_user_id=current_user.id,
            action="SIMULATOR_CHANGE_APPLIED",
            resource_type="SESSION",
            resource_id=sess.id,
            before_state={"time_slot_id": old_time_slot, "room_id": old_room, "teacher_id": old_teacher},
            after_state={"time_slot_id": sess.time_slot_id, "room_id": sess.room_id, "teacher_id": sess.teacher_id},
            reason=payload.reason,
        )
    )

    await db.commit()
    await db.refresh(sess)

    # Re-evaluate timetable conflicts
    analysis = await ConflictService.analyze_conflicts(payload.timetable_id, db)

    # Dispatch smart ripple notification
    sub_code = sess.subject.code if sess.subject else "Class"
    sec_name = sess.cohort_section.section_name if sess.cohort_section else ""
    alert_title = f"Schedule Adjustment: {sub_code} ({sec_name}) Rescheduled"
    alert_message = (
        f"{sub_code} for Section {sec_name} has been rescheduled to new time slot '{payload.proposed_time_slot_id}'. "
        f"Reason: {payload.reason}."
    )

    dispatched = await AlertEngineService.dispatch_timetable_change_alert(
        db=db,
        timetable_id=payload.timetable_id,
        title=alert_title,
        description=alert_message,
        affected_section_ids=[sess.cohort_section_id],
        affected_teacher_ids=[sess.teacher_id, old_teacher],
        change_diff={
            "session_id": sess.id,
            "old_time_slot": old_time_slot,
            "new_time_slot": payload.proposed_time_slot_id,
            "reason": payload.reason,
        },
        actor_user=current_user,
    )

    return {
        "status": "APPLIED",
        "session_id": sess.id,
        "new_time_slot_id": sess.time_slot_id,
        "is_conflict_free": analysis.get("is_conflict_free", True),
        "critical_conflicts_count": analysis.get("critical_conflicts_count", 0),
        "recipients_notified": len(dispatched),
        "message": f"Successfully applied schedule adjustment and dispatched {len(dispatched)} ripple alerts to affected faculty and students.",
    }
