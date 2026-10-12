import io
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pydantic import BaseModel
from app.api.deps import PermissionGuard, get_current_user
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.permissions import Permission, ROLE_PERMISSIONS_MAP
from app.db.session import get_db_session
from app.models.cohort import CohortSection
from app.models.curriculum import SubjectRequirement
from app.models.infrastructure import Room, TimeSlot
from app.models.preference import SchedulingPreference
from app.models.teacher import Teacher
from app.models.timetable import (
    SessionStatusEnum,
    Timetable,
    TimetableSession,
    TimetableStatusEnum,
)
from app.models.user import User, UserRoleEnum
from app.services.scheduler.engine import TimetableSolver
from app.services.scheduler.schemas import (
    CohortSectionInput,
    GenerateScheduleRequest,
    GenerateScheduleResponse,
    RoomScheduleInput,
    SchedulingConfig,
    SolverStatusEnum,
    SubjectRequirementInput,
    TeacherScheduleInput,
    TimeSlotInput,
)
from app.services.scheduler.validator import TimetableValidator

router = APIRouter(prefix="/timetables", tags=["Timetable Scheduling & Views"])


@router.post(
    "/generate",
    response_model=GenerateScheduleResponse,
    summary="Generate Timetable using OR-Tools CP-SAT",
    dependencies=[Depends(PermissionGuard(Permission.SOLVER_RUN))],
)
async def generate_timetable(
    request: GenerateScheduleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GenerateScheduleResponse:
    """
    Executes the CP-SAT timetable generation engine:
    1. Loads scheduling data for department & academic term.
    2. Solves with mandatory hard constraints and configurable soft preferences.
    3. Runs the independent validator to guarantee zero hard conflicts.
    4. Persists the verified draft timetable in PostgreSQL/SQLite.
    """
    # Department jurisdiction check
    user_depts = [s.department_id for s in current_user.department_scopes]
    if current_user.role not in {UserRoleEnum.ADMIN} and request.department_id not in user_depts:
        raise ForbiddenException("You cannot generate schedules for another department.")

    # 1. Fetch time slots
    slot_stmt = select(TimeSlot).order_by(TimeSlot.day_of_week, TimeSlot.period_number)
    slots_db = (await db.execute(slot_stmt)).scalars().all()
    if not slots_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No time slots configured in the institution.",
        )
    slots_input = [
        TimeSlotInput(
            id=s.id,
            day_of_week=s.day_of_week,
            period_number=s.period_number,
            is_break=s.is_break,
            start_time=s.start_time.strftime("%H:%M") if s.start_time else "",
            end_time=s.end_time.strftime("%H:%M") if s.end_time else "",
        )
        for s in slots_db
    ]

    # 2. Fetch rooms
    room_stmt = select(Room).where(Room.is_active == True)  # noqa: E712
    rooms_db = (await db.execute(room_stmt)).scalars().all()
    rooms_input = [
        RoomScheduleInput(
            id=r.id,
            building=r.building,
            room_number=r.room_number,
            capacity=r.capacity,
            room_type=r.room_type.value,
            is_active=r.is_active,
        )
        for r in rooms_db
    ]

    # 3. Fetch teachers & availabilities
    teach_stmt = select(Teacher).where(Teacher.department_id == request.department_id).options(
        selectinload(Teacher.availabilities), selectinload(Teacher.user)
    )
    teachers_db = (await db.execute(teach_stmt)).scalars().all()
    teachers_input = []
    for t in teachers_db:
        unavail = frozenset(a.time_slot_id for a in t.availabilities if not a.is_available)
        prefs = {a.time_slot_id: a.preference_weight for a in t.availabilities if a.is_available}
        teachers_input.append(
            TeacherScheduleInput(
                id=t.id,
                name=t.user.full_name if t.user else t.employee_code,
                max_hours_per_day=t.max_hours_per_day,
                max_consecutive_hours=t.max_consecutive_hours,
                max_weekly_hours=t.max_weekly_hours,
                unavailable_slot_ids=unavail,
                preference_weights=prefs,
            )
        )

    # 4. Fetch cohort sections
    cohort_stmt = select(CohortSection).where(
        CohortSection.department_id == request.department_id,
        CohortSection.academic_term_id == request.academic_term_id,
    )
    cohorts_db = (await db.execute(cohort_stmt)).scalars().all()
    cohorts_input = [
        CohortSectionInput(
            id=c.id,
            department_id=c.department_id,
            section_name=c.section_name,
            student_count=c.student_count,
        )
        for c in cohorts_db
    ]
    cohort_ids = [c.id for c in cohorts_db]

    # 5. Fetch subject requirements
    req_stmt = select(SubjectRequirement).where(
        SubjectRequirement.cohort_section_id.in_(cohort_ids)
    ).options(selectinload(SubjectRequirement.subject))
    reqs_db = (await db.execute(req_stmt)).scalars().all()
    reqs_input = [
        SubjectRequirementInput(
            id=rq.id,
            cohort_section_id=rq.cohort_section_id,
            subject_id=rq.subject_id,
            subject_code=rq.subject.code if rq.subject else "",
            subject_name=rq.subject.name if rq.subject else "",
            subject_type=rq.subject.subject_type.value if rq.subject else "THEORY",
            teacher_id=rq.teacher_id,
            required_room_type=rq.subject.required_room_type.value if rq.subject else "LECTURE_HALL",
            required_sessions_per_week=rq.required_sessions_per_week,
            duration_periods=rq.duration_periods,
            requires_consecutive_periods=rq.requires_consecutive_periods,
            preferred_room_id=rq.preferred_room_id,
        )
        for rq in reqs_db
    ]

    # 6. Fetch departmental preferences
    pref_stmt = select(SchedulingPreference).where(
        SchedulingPreference.department_id == request.department_id
    )
    pref_db = (await db.execute(pref_stmt)).scalars().first()

    config = SchedulingConfig(
        time_limit_seconds=request.time_limit_seconds,
        weight_preferred_times=request.weight_preferred_times or (pref_db.weight_preferred_times if pref_db else 10),
        weight_balanced_daily_workload=request.weight_balanced_daily_workload or (pref_db.weight_balanced_daily_workload if pref_db else 15),
        weight_minimize_gaps=request.weight_minimize_gaps or (pref_db.weight_minimize_gaps if pref_db else 10),
        max_daily_sessions_per_teacher=pref_db.max_daily_sessions_per_teacher if pref_db else 5,
        max_daily_sessions_per_cohort=pref_db.max_daily_sessions_per_cohort if pref_db else 6,
    )

    # 7. Run OR-Tools CP-SAT Solver
    solver = TimetableSolver(
        teachers=teachers_input,
        rooms=rooms_input,
        time_slots=slots_input,
        cohorts=cohorts_input,
        requirements=reqs_input,
        config=config,
    )
    solver_result = solver.solve()

    # 8. Run Independent Validator
    validator = TimetableValidator(
        teachers={t.id: t for t in teachers_input},
        rooms={r.id: r for r in rooms_input},
        time_slots={ts.id: ts for ts in slots_input},
        cohorts={c.id: c for c in cohorts_input},
        requirements={req.id: req for req in reqs_input},
    )
    validation_result = validator.validate(solver_result.sessions)

    # 9. If infeasible or invalid, return diagnostic response without creating corrupted draft
    if solver_result.status == SolverStatusEnum.INFEASIBLE or not validation_result.is_valid:
        return GenerateScheduleResponse(
            timetable_id="",
            status="FAILED",
            solver_status=solver_result.status.value,
            is_valid=validation_result.is_valid,
            wall_time_seconds=solver_result.wall_time_seconds,
            total_sessions_scheduled=len(solver_result.sessions),
            hard_violations=validation_result.hard_violations,
            soft_warnings=validation_result.soft_warnings,
            diagnostics=solver_result.diagnostics,
        )

    # 10. Persist Verified Timetable Draft to DB
    timetable_id = f"tt_{request.department_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    timetable = Timetable(
        id=timetable_id,
        department_id=request.department_id,
        academic_term_id=request.academic_term_id,
        version_major=1,
        version_minor=0,
        status=TimetableStatusEnum.DRAFT,
        solver_status=solver_result.status.value,
        solver_score={
            "objective_value": solver_result.objective_value,
            "metrics": solver_result.metrics,
        },
        created_by_user_id=current_user.id,
        notes=request.notes,
    )
    db.add(timetable)
    await db.flush()

    for idx, s in enumerate(solver_result.sessions):
        sess = TimetableSession(
            id=f"sess_{timetable_id}_{idx:03d}",
            timetable_id=timetable_id,
            requirement_id=s.requirement_id,
            cohort_section_id=s.cohort_section_id,
            subject_id=s.subject_id,
            teacher_id=s.teacher_id,
            room_id=s.room_id,
            time_slot_id=s.time_slot_id,
            status=SessionStatusEnum.OFFICIAL,
        )
        db.add(sess)

    await db.commit()

    return GenerateScheduleResponse(
        timetable_id=timetable_id,
        status="DRAFT",
        solver_status=solver_result.status.value,
        is_valid=True,
        wall_time_seconds=solver_result.wall_time_seconds,
        total_sessions_scheduled=len(solver_result.sessions),
        hard_violations=[],
        soft_warnings=validation_result.soft_warnings,
        diagnostics=[],
    )


@router.get(
    "/{timetable_id}/grid",
    summary="Get 2D Weekly Timetable Grid",
    dependencies=[Depends(PermissionGuard(Permission.TIMETABLE_VIEW_PUBLISHED))],
)
async def get_timetable_grid(
    timetable_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    section_id: str | None = Query(None, description="Filter by Section ID"),
    teacher_id: str | None = Query(None, description="Filter by Teacher ID"),
    room_id: str | None = Query(None, description="Filter by Room ID"),
) -> dict:
    """
    Returns weekly schedule formatted as a 2D matrix (Days 1-5 x Periods 1-6)
    with session cards containing subject code, name, teacher, room, and section.
    """
    tt_stmt = select(Timetable).where(Timetable.id == timetable_id)
    tt = (await db.execute(tt_stmt)).scalars().first()
    if not tt:
        raise NotFoundException("Timetable not found")

    # Scoping check: Unpublished timetables restricted to authorized coordinators / admins
    if tt.status != TimetableStatusEnum.PUBLISHED:
        user_perms = ROLE_PERMISSIONS_MAP.get(current_user.role, set())
        if current_user.role != UserRoleEnum.ADMIN and Permission.TIMETABLE_VIEW_DRAFT not in user_perms:
            raise ForbiddenException("Access to unpublished timetable draft is restricted to authorized coordinators and administrators.")

    # Scoping check: Student/CR can only view their own assigned section
    user_sections = [e.cohort_section_id for e in current_user.student_enrollments if e.is_active]
    if current_user.role in {UserRoleEnum.STUDENT, UserRoleEnum.CR}:
        if section_id and section_id not in user_sections:
            raise ForbiddenException("Access to this section is not permitted. Students may only view their assigned class/section.")
        if not section_id and user_sections:
            section_id = user_sections[0]

    # Fetch sessions with relationships
    sess_query = select(TimetableSession).where(TimetableSession.timetable_id == timetable_id).options(
        selectinload(TimetableSession.subject),
        selectinload(TimetableSession.cohort_section),
        selectinload(TimetableSession.teacher).selectinload(Teacher.user),
        selectinload(TimetableSession.room),
        selectinload(TimetableSession.time_slot),
    )
    if section_id:
        sess_query = sess_query.where(TimetableSession.cohort_section_id == section_id)
    if teacher_id:
        sess_query = sess_query.where(TimetableSession.teacher_id == teacher_id)
    if room_id:
        sess_query = sess_query.where(TimetableSession.room_id == room_id)

    sessions = (await db.execute(sess_query)).scalars().all()

    # Index sessions by (day, period)
    cells_by_slot = {}
    for s in sessions:
        slot = s.time_slot
        if slot:
            key = f"{slot.day_of_week}_{slot.period_number}"
            cells_by_slot[key] = {
                "session_id": s.id,
                "subject_id": s.subject_id,
                "subject_code": s.subject.code if s.subject else "",
                "subject_name": s.subject.name if s.subject else "",
                "subject_type": s.subject.subject_type.value if s.subject else "THEORY",
                "teacher_name": s.teacher.user.full_name if s.teacher and s.teacher.user else "",
                "teacher_id": s.teacher_id,
                "room_id": s.room_id,
                "room_name": f"{s.room.building} {s.room.room_number}" if s.room else "",
                "room_type": s.room.room_type.value if s.room else "",
                "section_id": s.cohort_section_id,
                "section_name": s.cohort_section.section_name if s.cohort_section else "",
                "time_slot_id": s.time_slot_id,
                "status": s.status.value,
                "is_locked": getattr(s, "is_locked", False),
            }

    # Build grid structure
    days_map = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}
    grid = []
    periods_header = [
        {"period": p, "is_break": (p == 4), "label": f"Period {p}" if p != 4 else "Lunch Break"}
        for p in range(1, 7)
    ]

    for day_num in range(1, 6):
        day_row = {
            "day_number": day_num,
            "day_name": days_map.get(day_num, f"Day {day_num}"),
            "periods": [],
        }
        for p in range(1, 7):
            key = f"{day_num}_{p}"
            day_row["periods"].append({
                "period_number": p,
                "is_break": (p == 4),
                "session": cells_by_slot.get(key, None),
            })
        grid.append(day_row)

    return {
        "timetable_id": tt.id,
        "department_id": tt.department_id,
        "status": tt.status.value,
        "version": f"v{tt.version_major}.{tt.version_minor}",
        "periods_header": periods_header,
        "grid": grid,
        "total_sessions": len(sessions),
    }


@router.get(
    "/{timetable_id}/export",
    summary="Export Timetable as CSV or XLSX",
    dependencies=[Depends(PermissionGuard(Permission.TIMETABLE_VIEW_PUBLISHED))],
)
async def export_timetable(
    timetable_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    export_format: str = Query("csv", regex="^(csv|xlsx)$"),
    section_id: str | None = Query(None),
) -> Response:
    """
    Exports the verified timetable schedule as CSV or formatted Excel file.
    """
    tt_stmt = select(Timetable).where(Timetable.id == timetable_id)
    tt = (await db.execute(tt_stmt)).scalars().first()
    if not tt:
        raise NotFoundException("Timetable not found")

    if tt.status != TimetableStatusEnum.PUBLISHED:
        user_perms = ROLE_PERMISSIONS_MAP.get(current_user.role, set())
        if current_user.role != UserRoleEnum.ADMIN and Permission.TIMETABLE_VIEW_DRAFT not in user_perms:
            raise ForbiddenException("Access to export unpublished timetable draft is restricted.")

    user_sections = [e.cohort_section_id for e in current_user.student_enrollments if e.is_active]
    if current_user.role in {UserRoleEnum.STUDENT, UserRoleEnum.CR}:
        if section_id and section_id not in user_sections:
            raise ForbiddenException("Access to export this section is not permitted.")
        if not section_id and user_sections:
            section_id = user_sections[0]

    sess_query = select(TimetableSession).where(TimetableSession.timetable_id == timetable_id).options(
        selectinload(TimetableSession.subject),
        selectinload(TimetableSession.cohort_section),
        selectinload(TimetableSession.teacher).selectinload(Teacher.user),
        selectinload(TimetableSession.room),
        selectinload(TimetableSession.time_slot),
    )
    if section_id:
        sess_query = sess_query.where(TimetableSession.cohort_section_id == section_id)

    sessions = (await db.execute(sess_query)).scalars().all()

    days_map = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}
    rows = []
    for s in sessions:
        slot = s.time_slot
        rows.append({
            "Day": days_map.get(slot.day_of_week, f"Day {slot.day_of_week}") if slot else "",
            "Period": slot.period_number if slot else "",
            "Time": f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}" if slot and slot.start_time else "",
            "Section": s.cohort_section.section_name if s.cohort_section else "",
            "Subject Code": s.subject.code if s.subject else "",
            "Subject Name": s.subject.name if s.subject else "",
            "Type": s.subject.subject_type.value if s.subject else "",
            "Teacher": s.teacher.user.full_name if s.teacher and s.teacher.user else "",
            "Room": f"{s.room.building} {s.room.room_number}" if s.room else "",
            "Status": s.status.value,
        })

    # Sort rows by Day and Period
    rows.sort(key=lambda r: (r["Day"], r["Period"]))
    df = pd.DataFrame(rows)

    if export_format == "xlsx":
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Timetable Schedule")
        return StreamingResponse(
            io.BytesIO(out.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=timetable_{timetable_id}.xlsx"},
        )
    else:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=timetable_{timetable_id}.csv"},
        )


@router.get(
    "",
    summary="List Timetables with Versions and Statuses",
)
async def list_timetables(
    department_id: str | None = Query(None, description="Department ID"),
    academic_term_id: str | None = Query(None, description="Academic Term ID"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> list[dict]:
    """Lists timetable records ordered by creation date desc with version info."""
    stmt = select(Timetable).order_by(Timetable.version_major.desc(), Timetable.version_minor.desc())
    if department_id:
        stmt = stmt.where(Timetable.department_id == department_id)
    if academic_term_id:
        stmt = stmt.where(Timetable.academic_term_id == academic_term_id)

    # Scoping for non-admins
    if current_user and current_user.role not in {UserRoleEnum.ADMIN}:
        user_depts = [s.department_id for s in current_user.department_scopes]
        if user_depts:
            stmt = stmt.where(Timetable.department_id.in_(user_depts))
        # Non-administrative users (students, CR, regular teachers) only see published timetables
        user_perms = ROLE_PERMISSIONS_MAP.get(current_user.role, set())
        if Permission.TIMETABLE_VIEW_DRAFT not in user_perms:
            stmt = stmt.where(Timetable.status == TimetableStatusEnum.PUBLISHED)

    tables = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": t.id,
            "department_id": t.department_id,
            "academic_term_id": t.academic_term_id,
            "version": f"v{t.version_major}.{t.version_minor}",
            "version_major": t.version_major,
            "version_minor": t.version_minor,
            "lock_version": t.lock_version,
            "parent_version_id": t.parent_version_id,
            "status": t.status.value,
            "solver_status": t.solver_status,
            "published_at": t.published_at.isoformat() if t.published_at else None,
            "created_at": t.created_at.isoformat(),
            "notes": t.notes,
        }
        for t in tables
    ]


@router.post(
    "/{timetable_id}/propose",
    summary="Propose Draft Timetable for Review",
    dependencies=[Depends(PermissionGuard(Permission.SOLVER_RUN))],
)
async def propose_timetable(
    timetable_id: str,
    notes: str | None = Query(None, description="Proposal notes"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict:
    """Validates and transitions a DRAFT timetable to PROPOSED state."""
    from app.services.approvals.approval_service import ApprovalService

    table = await ApprovalService.propose_draft(timetable_id, notes, current_user, db)
    return {
        "id": table.id,
        "status": table.status.value,
        "version": f"v{table.version_major}.{table.version_minor}",
        "message": "Draft timetable validated and proposed for authorized review.",
    }


@router.post(
    "/{timetable_id}/publish",
    summary="Approve and Publish Timetable officially",
    dependencies=[Depends(PermissionGuard(Permission.TIMETABLE_APPROVE))],
)
async def publish_timetable(
    timetable_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """
    Authorized HOD / College Management approval and publication.
    Enforces that timetable must be verified conflict-free before publishing.
    """
    from app.services.scheduler.conflict_service import ConflictService

    analysis = await ConflictService.analyze_conflicts(timetable_id, db)
    if not analysis["is_conflict_free"]:
        raise ValidationException(
            f"Cannot publish timetable: {analysis['critical_conflicts_count']} hard constraint violations detected. "
            "Resolve all conflicts prior to official publication."
        )

    stmt = select(Timetable).where(Timetable.id == timetable_id)
    tt_res = await db.execute(stmt)
    table = tt_res.scalars().first()
    if not table:
        raise NotFoundException(f"Timetable '{timetable_id}' not found.")

    table.status = TimetableStatusEnum.PUBLISHED
    table.approved_by_user_id = current_user.id
    table.published_at = datetime.now(UTC)

    # Protect locked sessions upon approval
    sess_stmt = select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
    all_sessions = (await db.execute(sess_stmt)).scalars().all()
    affected_sections = list(set(s.cohort_section_id for s in all_sessions if s.cohort_section_id))
    affected_teachers = list(set(s.teacher_id for s in all_sessions if s.teacher_id))
    for s in all_sessions:
        s.is_locked = True

    await db.commit()
    await db.refresh(table)

    # Dispatch smart ripple notification to affected users
    try:
        from app.services.alerts.alert_engine import AlertEngineService
        await AlertEngineService.dispatch_timetable_change_alert(
            db=db,
            timetable_id=timetable_id,
            title=f"Official Timetable Published: Version v{table.version_major}.{table.version_minor}",
            description=f"The official academic timetable for department '{table.department_id}' has been approved and published by {current_user.full_name}. All sessions are officially confirmed.",
            affected_section_ids=affected_sections,
            affected_teacher_ids=affected_teachers,
            change_diff={"version": f"v{table.version_major}.{table.version_minor}", "total_sessions": len(all_sessions)},
            actor_user=current_user,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to dispatch publish ripple alert: {e}")

    return {
        "id": table.id,
        "status": table.status.value,
        "version": f"v{table.version_major}.{table.version_minor}",
        "published_at": table.published_at.isoformat() if table.published_at else None,
        "message": f"Timetable version v{table.version_major}.{table.version_minor} has been verified and published officially.",
    }


@router.get(
    "/compare/diff",
    summary="Compare Two Timetable Versions Side-by-Side",
)
async def compare_timetable_versions(
    version_a_id: str = Query(..., description="First timetable version ID"),
    version_b_id: str = Query(..., description="Second timetable version ID"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
):
    """Compares two timetable versions and identifies added, removed, and modified sessions."""
    from app.services.approvals.approval_service import ApprovalService

    return await ApprovalService.compare_versions(version_a_id, version_b_id, current_user, db)


@router.post(
    "/{timetable_id}/rollback",
    summary="Safely Restore a Prior Timetable Version",
    dependencies=[Depends(PermissionGuard(Permission.TIMETABLE_RESTORE))],
)
async def rollback_timetable(
    timetable_id: str,
    payload: dict,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
):
    """
    Safely restores a prior version by creating a NEW validated version,
    never destructively deleting history.
    """
    from app.services.approvals.approval_service import ApprovalService
    from app.services.approvals.schemas import RollbackRequest

    req = RollbackRequest(
        target_version_id=payload.get("target_version_id", ""),
        reason=payload.get("reason", "Administrative rollback"),
    )
    new_table = await ApprovalService.rollback_version(timetable_id, req, current_user, db)
    return {
        "id": new_table.id,
        "version": f"v{new_table.version_major}.{new_table.version_minor}",
        "status": new_table.status.value,
        "message": f"Successfully restored schedule to new version v{new_table.version_major}.{new_table.version_minor}.",
    }


# ==========================================
# SCHEDULE ENTRY CRUD & CONFLICT DETECTION
# ==========================================

class SessionCreateRequest(BaseModel):
    subject_id: str
    teacher_id: str
    room_id: str
    cohort_section_id: str
    time_slot_id: str


class SessionUpdateRequest(BaseModel):
    subject_id: str | None = None
    teacher_id: str | None = None
    room_id: str | None = None
    cohort_section_id: str | None = None
    time_slot_id: str | None = None


class SessionConflictCheckRequest(BaseModel):
    timetable_id: str
    time_slot_id: str
    teacher_id: str
    room_id: str
    cohort_section_id: str
    session_id: str | None = None


class SessionConflictCheckResponse(BaseModel):
    has_conflict: bool
    conflicts: list[str]
    warnings: list[str]


async def detect_session_conflicts(
    db: AsyncSession,
    timetable_id: str,
    time_slot_id: str,
    teacher_id: str,
    room_id: str,
    cohort_section_id: str,
    exclude_session_id: str | None = None,
) -> tuple[list[str], list[str]]:
    conflicts: list[str] = []
    warnings: list[str] = []

    # 1. Validate slot exists and is not a break
    slot_stmt = select(TimeSlot).where(TimeSlot.id == time_slot_id)
    slot = (await db.execute(slot_stmt)).scalars().first()
    if not slot:
        conflicts.append("Selected time slot does not exist.")
        return conflicts, warnings
    if slot.is_break:
        conflicts.append("Cannot schedule academic classes during designated recess or lunch break.")

    # 2. Check Teacher Double-Booking
    teacher_conflict_stmt = (
        select(TimetableSession)
        .options(selectinload(TimetableSession.subject), selectinload(TimetableSession.room))
        .where(
            TimetableSession.timetable_id == timetable_id,
            TimetableSession.time_slot_id == time_slot_id,
            TimetableSession.teacher_id == teacher_id,
        )
    )
    if exclude_session_id:
        teacher_conflict_stmt = teacher_conflict_stmt.where(TimetableSession.id != exclude_session_id)
    existing_t = (await db.execute(teacher_conflict_stmt)).scalars().first()
    if existing_t:
        sub_name = existing_t.subject.name if existing_t.subject else "another class"
        rm_name = f"{existing_t.room.building} {existing_t.room.room_number}" if existing_t.room else "another room"
        conflicts.append(f"Faculty Double-Booking: Instructor is already scheduled for '{sub_name}' in {rm_name} during this period.")

    # 3. Check Room Double-Booking
    room_conflict_stmt = (
        select(TimetableSession)
        .options(selectinload(TimetableSession.cohort_section), selectinload(TimetableSession.subject))
        .where(
            TimetableSession.timetable_id == timetable_id,
            TimetableSession.time_slot_id == time_slot_id,
            TimetableSession.room_id == room_id,
        )
    )
    if exclude_session_id:
        room_conflict_stmt = room_conflict_stmt.where(TimetableSession.id != exclude_session_id)
    existing_r = (await db.execute(room_conflict_stmt)).scalars().first()
    if existing_r:
        sec_name = existing_r.cohort_section.section_name if existing_r.cohort_section else "another section"
        sub_name = existing_r.subject.name if existing_r.subject else "class"
        conflicts.append(f"Room Double-Booking: Room is already booked by Section {sec_name} ({sub_name}) during this period.")

    # 4. Check Section Double-Booking
    section_conflict_stmt = (
        select(TimetableSession)
        .options(selectinload(TimetableSession.subject))
        .where(
            TimetableSession.timetable_id == timetable_id,
            TimetableSession.time_slot_id == time_slot_id,
            TimetableSession.cohort_section_id == cohort_section_id,
        )
    )
    if exclude_session_id:
        section_conflict_stmt = section_conflict_stmt.where(TimetableSession.id != exclude_session_id)
    existing_s = (await db.execute(section_conflict_stmt)).scalars().first()
    if existing_s:
        sub_name = existing_s.subject.name if existing_s.subject else "another lecture"
        conflicts.append(f"Cohort Conflict: Section already has scheduled session '{sub_name}' during this period.")

    # 5. Room Capacity Warning
    room_stmt = select(Room).where(Room.id == room_id)
    room_obj = (await db.execute(room_stmt)).scalars().first()
    cohort_stmt = select(CohortSection).where(CohortSection.id == cohort_section_id)
    cohort_obj = (await db.execute(cohort_stmt)).scalars().first()
    if room_obj and cohort_obj and room_obj.capacity < cohort_obj.student_count:
        warnings.append(f"Capacity Warning: Room seating capacity ({room_obj.capacity}) is less than section enrollment ({cohort_obj.student_count}).")

    return conflicts, warnings


@router.post("/sessions/check-conflict", response_model=SessionConflictCheckResponse)
async def check_session_conflict(
    payload: SessionConflictCheckRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> SessionConflictCheckResponse:
    """Real-time conflict preflight endpoint for client forms before submission."""
    conflicts, warnings = await detect_session_conflicts(
        db=db,
        timetable_id=payload.timetable_id,
        time_slot_id=payload.time_slot_id,
        teacher_id=payload.teacher_id,
        room_id=payload.room_id,
        cohort_section_id=payload.cohort_section_id,
        exclude_session_id=payload.session_id,
    )
    return SessionConflictCheckResponse(
        has_conflict=len(conflicts) > 0,
        conflicts=conflicts,
        warnings=warnings,
    )


@router.get("/{timetable_id}/options", summary="Get Available Entities for Schedule Forms")
async def get_schedule_form_options(
    timetable_id: str,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict:
    """Returns subjects, faculty teachers, rooms, cohorts, and time slots to populate client forms."""
    tt_stmt = select(Timetable).where(Timetable.id == timetable_id)
    tt = (await db.execute(tt_stmt)).scalars().first()
    if not tt:
        raise NotFoundException("Timetable not found")

    from app.models.curriculum import Subject
    subs = (await db.execute(select(Subject).where(Subject.department_id == tt.department_id))).scalars().all()
    teachers = (await db.execute(
        select(Teacher).options(selectinload(Teacher.user))
    )).scalars().all()
    rooms = (await db.execute(select(Room).where(Room.is_active == True))).scalars().all()  # noqa: E712
    cohorts = (await db.execute(select(CohortSection).where(CohortSection.department_id == tt.department_id))).scalars().all()
    slots = (await db.execute(select(TimeSlot).order_by(TimeSlot.day_of_week, TimeSlot.period_number))).scalars().all()

    return {
        "subjects": [{"id": s.id, "code": s.code, "name": s.name, "type": s.subject_type.value} for s in subs],
        "teachers": [{"id": t.id, "name": t.user.full_name if t.user else t.employee_code, "employee_code": t.employee_code} for t in teachers],
        "rooms": [{"id": r.id, "number": f"{r.building} {r.room_number}", "capacity": r.capacity, "type": r.room_type.value} for r in rooms],
        "cohorts": [{"id": c.id, "name": f"{c.program_name} {c.section_name}", "section_name": c.section_name} for c in cohorts],
        "time_slots": [
            {
                "id": sl.id,
                "day_of_week": sl.day_of_week,
                "period_number": sl.period_number,
                "is_break": sl.is_break,
                "start_time": sl.start_time.strftime("%H:%M") if sl.start_time else "",
                "end_time": sl.end_time.strftime("%H:%M") if sl.end_time else "",
            }
            for sl in slots
        ],
    }


@router.post("/{timetable_id}/sessions", status_code=status.HTTP_201_CREATED)
async def create_schedule_session(
    timetable_id: str,
    payload: SessionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict:
    """Authorized manual creation of a schedule entry with strict conflict validation."""
    ALLOWED_MANAGE_ROLES = {
        UserRoleEnum.ADMIN,
        UserRoleEnum.HOD,
        UserRoleEnum.COORDINATOR,
    }
    if current_user and current_user.role not in ALLOWED_MANAGE_ROLES:
        raise ForbiddenException("You do not have permission to create schedule sessions. Timetables can only be edited by authorized HOD or Timetable Coordinators.")

    tt_stmt = select(Timetable).where(Timetable.id == timetable_id)
    tt = (await db.execute(tt_stmt)).scalars().first()
    if not tt:
        raise NotFoundException(f"Timetable '{timetable_id}' not found.")

    conflicts, _ = await detect_session_conflicts(
        db=db,
        timetable_id=timetable_id,
        time_slot_id=payload.time_slot_id,
        teacher_id=payload.teacher_id,
        room_id=payload.room_id,
        cohort_section_id=payload.cohort_section_id,
    )
    if conflicts:
        raise ConflictException(detail="; ".join(conflicts))

    session_id = f"sess_{timetable_id}_{int(time.time()*1000)%1000000:06d}"
    sess = TimetableSession(
        id=session_id,
        timetable_id=timetable_id,
        requirement_id=None,
        cohort_section_id=payload.cohort_section_id,
        subject_id=payload.subject_id,
        teacher_id=payload.teacher_id,
        room_id=payload.room_id,
        time_slot_id=payload.time_slot_id,
        status=SessionStatusEnum.OFFICIAL,
    )
    db.add(sess)
    await db.commit()

    # Re-fetch with relationships
    created = (await db.execute(
        select(TimetableSession)
        .options(
            selectinload(TimetableSession.subject),
            selectinload(TimetableSession.teacher).selectinload(Teacher.user),
            selectinload(TimetableSession.room),
            selectinload(TimetableSession.cohort_section),
            selectinload(TimetableSession.time_slot),
        )
        .where(TimetableSession.id == session_id)
    )).scalars().first()

    return {
        "id": created.id,
        "session_id": created.id,
        "subject_code": created.subject.code if created.subject else "",
        "subject_name": created.subject.name if created.subject else "",
        "teacher_name": created.teacher.user.full_name if created.teacher and created.teacher.user else "",
        "room_name": f"{created.room.building} {created.room.room_number}" if created.room else "",
        "section_name": created.cohort_section.section_name if created.cohort_section else "",
        "time_slot_id": created.time_slot_id,
        "message": "Schedule entry added successfully.",
    }


@router.put("/{timetable_id}/sessions/{session_id}")
async def update_schedule_session(
    timetable_id: str,
    session_id: str,
    payload: SessionUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict:
    """Authorized update of an existing schedule session with conflict re-validation."""
    ALLOWED_MANAGE_ROLES = {
        UserRoleEnum.ADMIN,
        UserRoleEnum.HOD,
        UserRoleEnum.COORDINATOR,
    }
    if current_user and current_user.role not in ALLOWED_MANAGE_ROLES:
        raise ForbiddenException("You do not have permission to modify schedule sessions. Timetables can only be edited by authorized HOD or Timetable Coordinators.")

    sess_stmt = select(TimetableSession).where(
        TimetableSession.id == session_id,
        TimetableSession.timetable_id == timetable_id,
    )
    sess = (await db.execute(sess_stmt)).scalars().first()
    if not sess:
        raise NotFoundException(f"Session '{session_id}' not found in timetable '{timetable_id}'.")

    if sess.is_locked:
        raise ConflictException(detail="Session is locked by administrative approval. Please unlock the session before modifying it.")

    new_time_slot = payload.time_slot_id or sess.time_slot_id
    new_teacher = payload.teacher_id or sess.teacher_id
    new_room = payload.room_id or sess.room_id
    new_cohort = payload.cohort_section_id or sess.cohort_section_id
    new_subject = payload.subject_id or sess.subject_id

    conflicts, _ = await detect_session_conflicts(
        db=db,
        timetable_id=timetable_id,
        time_slot_id=new_time_slot,
        teacher_id=new_teacher,
        room_id=new_room,
        cohort_section_id=new_cohort,
        exclude_session_id=session_id,
    )
    if conflicts:
        raise ConflictException(detail="; ".join(conflicts))

    sess.time_slot_id = new_time_slot
    sess.teacher_id = new_teacher
    sess.room_id = new_room
    sess.cohort_section_id = new_cohort
    sess.subject_id = new_subject

    await db.commit()

    return {
        "id": sess.id,
        "session_id": sess.id,
        "message": "Schedule entry updated successfully.",
    }


@router.delete("/{timetable_id}/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def delete_schedule_session(
    timetable_id: str,
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict:
    """Authorized deletion of an individual schedule entry."""
    ALLOWED_MANAGE_ROLES = {
        UserRoleEnum.ADMIN,
        UserRoleEnum.HOD,
        UserRoleEnum.COORDINATOR,
    }
    if current_user and current_user.role not in ALLOWED_MANAGE_ROLES:
        raise ForbiddenException("You do not have permission to delete schedule entries. Timetables can only be edited by authorized HOD or Timetable Coordinators.")

    sess_stmt = select(TimetableSession).where(
        TimetableSession.id == session_id,
        TimetableSession.timetable_id == timetable_id,
    )
    sess = (await db.execute(sess_stmt)).scalars().first()
    if not sess:
        raise NotFoundException(f"Session '{session_id}' not found in timetable '{timetable_id}'.")

    if sess.is_locked:
        raise ConflictException(detail="Session is locked by administrative approval. Please unlock the session before deleting it.")

    await db.delete(sess)
    await db.commit()

    return {
        "message": "Schedule entry deleted successfully.",
        "session_id": session_id,
    }


class SessionLockToggleRequest(BaseModel):
    is_locked: bool


@router.patch("/{timetable_id}/sessions/{session_id}/lock", summary="Lock or Unlock Session")
async def toggle_session_lock(
    timetable_id: str,
    session_id: str,
    payload: SessionLockToggleRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict:
    """
    Lock or unlock a timetable session. Locked sessions are protected from automated moves and rescheduling.
    """
    ALLOWED_LOCK_ROLES = {
        UserRoleEnum.ADMIN,
        UserRoleEnum.HOD,
        UserRoleEnum.COORDINATOR,
    }
    if current_user and current_user.role not in ALLOWED_LOCK_ROLES:
        raise ForbiddenException("You do not have permission to lock or unlock timetable sessions. Timetables can only be managed by authorized HOD or Timetable Coordinators.")

    sess_stmt = select(TimetableSession).where(
        TimetableSession.id == session_id,
        TimetableSession.timetable_id == timetable_id,
    )
    sess = (await db.execute(sess_stmt)).scalars().first()
    if not sess:
        raise NotFoundException(f"Session '{session_id}' not found in timetable '{timetable_id}'.")

    sess.is_locked = payload.is_locked
    await db.commit()

    return {
        "session_id": sess.id,
        "is_locked": sess.is_locked,
        "message": f"Session {'locked (protected from automatic rescheduling)' if sess.is_locked else 'unlocked'}.",
    }


@router.get("/{timetable_id}/day/{day_number}", summary="Get Single Day Timetable Schedule")
async def get_day_timetable(
    timetable_id: str,
    day_number: int,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    section_id: str | None = Query(None),
) -> dict:
    """Returns chronological schedule for a single day (1=Monday .. 6=Saturday)."""
    days_map = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}

    tt_stmt = select(Timetable).where(Timetable.id == timetable_id)
    tt = (await db.execute(tt_stmt)).scalars().first()
    if not tt:
        raise NotFoundException("Timetable not found")

    if tt.status != TimetableStatusEnum.PUBLISHED:
        user_perms = ROLE_PERMISSIONS_MAP.get(current_user.role, set())
        if current_user.role != UserRoleEnum.ADMIN and Permission.TIMETABLE_VIEW_DRAFT not in user_perms:
            raise ForbiddenException("Access to unpublished timetable draft is restricted.")

    # Scoping check
    user_sections = [e.cohort_section_id for e in current_user.student_enrollments if e.is_active]
    if current_user.role in {UserRoleEnum.STUDENT, UserRoleEnum.CR}:
        if section_id and section_id not in user_sections:
            raise ForbiddenException("Access to this section is not permitted.")
        if not section_id and user_sections:
            section_id = user_sections[0]

    # Time slots for this day
    slots_stmt = (
        select(TimeSlot)
        .where(TimeSlot.day_of_week == day_number)
        .order_by(TimeSlot.period_number)
    )
    slots = (await db.execute(slots_stmt)).scalars().all()

    # Sessions for this day & timetable
    sess_stmt = (
        select(TimetableSession)
        .join(TimeSlot, TimetableSession.time_slot_id == TimeSlot.id)
        .options(
            selectinload(TimetableSession.subject),
            selectinload(TimetableSession.cohort_section),
            selectinload(TimetableSession.teacher).selectinload(Teacher.user),
            selectinload(TimetableSession.room),
            selectinload(TimetableSession.time_slot),
        )
        .where(
            TimetableSession.timetable_id == timetable_id,
            TimeSlot.day_of_week == day_number,
        )
    )
    if section_id:
        sess_stmt = sess_stmt.where(TimetableSession.cohort_section_id == section_id)

    sessions = (await db.execute(sess_stmt)).scalars().all()
    sessions_by_period = {s.time_slot.period_number: s for s in sessions if s.time_slot}

    timeline = []
    for sl in slots:
        sess = sessions_by_period.get(sl.period_number)
        timeline.append({
            "period_number": sl.period_number,
            "is_break": sl.is_break,
            "start_time": sl.start_time.strftime("%H:%M") if sl.start_time else "",
            "end_time": sl.end_time.strftime("%H:%M") if sl.end_time else "",
            "session": {
                "session_id": sess.id,
                "subject_code": sess.subject.code if sess.subject else "",
                "subject_name": sess.subject.name if sess.subject else "",
                "subject_type": sess.subject.subject_type.value if sess.subject else "THEORY",
                "teacher_id": sess.teacher_id,
                "teacher_name": sess.teacher.user.full_name if sess.teacher and sess.teacher.user else "",
                "room_id": sess.room_id,
                "room_name": f"{sess.room.building} {sess.room.room_number}" if sess.room else "",
                "room_type": sess.room.room_type.value if sess.room else "",
                "section_id": sess.cohort_section_id,
                "section_name": sess.cohort_section.section_name if sess.cohort_section else "",
                "status": sess.status.value,
                "is_locked": getattr(sess, "is_locked", False),
            } if sess else None,
        })

    return {
        "timetable_id": timetable_id,
        "day_number": day_number,
        "day_name": days_map.get(day_number, f"Day {day_number}"),
        "timeline": timeline,
    }


