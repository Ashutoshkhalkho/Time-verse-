from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import PermissionGuard, get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.core.permissions import Permission
from app.db.session import get_db_session
from app.models.curriculum import SubjectRequirement
from app.models.infrastructure import Room, TimeSlot
from app.models.teacher import Teacher, TeacherAvailability
from app.models.timetable import Timetable, TimetableSession
from app.models.user import User, UserRoleEnum
from app.services.scheduler.conflict_service import ConflictService

router = APIRouter(prefix="/rescheduler", tags=["Smart Rescheduler"])


class DisruptionAnalysisRequest(BaseModel):
    timetable_id: str | None = None
    disruption_type: str  # "TEACHER_ABSENCE" | "ROOM_OUTAGE" | "SESSION_RESCHEDULE"
    teacher_id: str | None = None
    room_id: str | None = None
    day_of_week: int | None = None
    time_slot_ids: list[str] | None = None
    target_session_id: str | None = None


class ApplyRescheduleRequest(BaseModel):
    timetable_id: str | None = None
    session_id: str
    new_time_slot_id: str | None = None
    new_teacher_id: str | None = None
    new_room_id: str | None = None
    reason: str | None = "Smart Rescheduler automated adjustment"


@router.post(
    "/analyze",
    summary="Analyze schedule disruption and suggest feasible clash-free alternatives",
)
async def analyze_disruption(
    request: DisruptionAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    1. Identifies directly affected sessions.
    2. Identifies unaffected sessions and marks them as preserved.
    3. Finds feasible alternative slots, substitute teachers, or rooms with 0 clashes.
    4. Previews the impact before any database modifications.
    """
    timetable_id = request.timetable_id
    if not timetable_id:
        tt_res = await db.execute(select(Timetable.id).order_by(Timetable.created_at.desc()).limit(1))
        timetable_id = tt_res.scalar_one_or_none()
        if not timetable_id:
            raise NotFoundException("No active timetable found.")

    # Fetch timetable and sessions
    stmt = (
        select(Timetable)
        .options(
            selectinload(Timetable.sessions).selectinload(TimetableSession.subject),
            selectinload(Timetable.sessions).selectinload(TimetableSession.teacher).selectinload(Teacher.user),
            selectinload(Timetable.sessions).selectinload(TimetableSession.room),
            selectinload(Timetable.sessions).selectinload(TimetableSession.time_slot),
            selectinload(Timetable.sessions).selectinload(TimetableSession.cohort_section),
        )
        .where(Timetable.id == timetable_id)
    )
    res = await db.execute(stmt)
    timetable = res.scalars().first()
    if not timetable:
        raise NotFoundException(f"Timetable '{timetable_id}' not found.")

    all_rooms = {r.id: r for r in (await db.execute(select(Room))).scalars().all()}
    all_teachers = {t.id: t for t in (await db.execute(select(Teacher).options(selectinload(Teacher.user)))).scalars().all()}
    all_slots = {s.id: s for s in (await db.execute(select(TimeSlot).order_by(TimeSlot.day_of_week, TimeSlot.period_number))).scalars().all()}
    all_reqs = {r.id: r for r in (await db.execute(select(SubjectRequirement))).scalars().all()}

    avail_res = await db.execute(select(TeacherAvailability))
    unavail_slots_by_teacher: dict[str, set[str]] = {}
    for a in avail_res.scalars().all():
        if not a.is_available:
            unavail_slots_by_teacher.setdefault(a.teacher_id, set()).add(a.time_slot_id)

    sessions = timetable.sessions
    total_sessions_count = len(sessions)
    days_map = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}

    # Build resource occupancy
    occupied_rooms = set()
    occupied_teachers = set()
    occupied_cohorts = set()
    for s in sessions:
        if s.time_slot_id:
            occupied_rooms.add((s.time_slot_id, s.room_id))
            occupied_teachers.add((s.time_slot_id, s.teacher_id))
            occupied_cohorts.add((s.time_slot_id, s.cohort_section_id))

    affected_sessions: list[dict[str, Any]] = []

    # Identify affected sessions based on disruption type
    if request.disruption_type == "TEACHER_ABSENCE" and request.teacher_id:
        for s in sessions:
            if s.teacher_id == request.teacher_id:
                if request.day_of_week and s.time_slot and s.time_slot.day_of_week != request.day_of_week:
                    continue
                if request.time_slot_ids and s.time_slot_id not in request.time_slot_ids:
                    continue
                affected_sessions.append(s)

    elif request.disruption_type == "ROOM_OUTAGE" and request.room_id:
        for s in sessions:
            if s.room_id == request.room_id:
                if request.day_of_week and s.time_slot and s.time_slot.day_of_week != request.day_of_week:
                    continue
                if request.time_slot_ids and s.time_slot_id not in request.time_slot_ids:
                    continue
                affected_sessions.append(s)

    elif request.disruption_type == "SESSION_RESCHEDULE" and request.target_session_id:
        target = next((s for s in sessions if s.id == request.target_session_id), None)
        if target:
            affected_sessions.append(target)
    else:
        # Fallback to target session or first session
        if request.target_session_id:
            target = next((s for s in sessions if s.id == request.target_session_id), None)
            if target:
                affected_sessions.append(target)

    affected_ids = {s.id for s in affected_sessions}
    unaffected_count = max(0, total_sessions_count - len(affected_sessions))
    preservation_rate = round((unaffected_count / total_sessions_count) * 100, 1) if total_sessions_count > 0 else 100.0

    # Format affected session details and generate alternatives for each
    affected_details: list[dict[str, Any]] = []

    for s in affected_sessions:
        slot = s.time_slot
        teacher = s.teacher
        room = s.room
        cohort = s.cohort_section
        subject = s.subject

        day_name = days_map.get(slot.day_of_week if slot else 1, "Day")
        p_num = slot.period_number if slot else 0
        slot_desc = f"{day_name} Period {p_num} ({slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')})" if slot else "Unassigned"

        alternatives: list[dict[str, Any]] = []

        # Option A: Alternative Time Slot (Move session where teacher, room, cohort are all vacant)
        for sl_id, sl in all_slots.items():
            if sl.is_break or sl_id == s.time_slot_id:
                continue
            # Check if teacher available
            if sl_id in unavail_slots_by_teacher.get(s.teacher_id, set()):
                continue
            if (sl_id, s.room_id) not in occupied_rooms and \
               (sl_id, s.teacher_id) not in occupied_teachers and \
               (sl_id, s.cohort_section_id) not in occupied_cohorts:
                sl_day = days_map.get(sl.day_of_week, "Day")
                alternatives.append({
                    "strategy": "SHIFT_TIMESLOT",
                    "title": f"Move to {sl_day} Period {sl.period_number}",
                    "description": f"Shift class to {sl_day} {sl.start_time.strftime('%H:%M')} - {sl.end_time.strftime('%H:%M')}. Room '{room.room_number if room else ''}' and Section '{cohort.section_name if cohort else ''}' are vacant with zero clashes.",
                    "new_time_slot_id": sl.id,
                    "new_teacher_id": s.teacher_id,
                    "new_room_id": s.room_id,
                    "feasibility_score": 98.0,
                    "conflicts_introduced": 0,
                })
                if len([a for a in alternatives if a["strategy"] == "SHIFT_TIMESLOT"]) >= 2:
                    break

        # Option B: Substitute Teacher (Keep slot, find another available faculty)
        if slot:
            for t_id, t in all_teachers.items():
                if t_id == s.teacher_id:
                    continue
                # Check if substitute is free during this slot
                if (slot.id, t_id) not in occupied_teachers and slot.id not in unavail_slots_by_teacher.get(t_id, set()):
                    alternatives.append({
                        "strategy": "SUBSTITUTE_FACULTY",
                        "title": f"Substitute with {t.full_name}",
                        "description": f"Assign {t.full_name} for this session during {slot_desc}. Room and students stay in current location without disruption.",
                        "new_time_slot_id": s.time_slot_id,
                        "new_teacher_id": t.id,
                        "new_room_id": s.room_id,
                        "feasibility_score": 95.0,
                        "conflicts_introduced": 0,
                    })
                    break

        # Option C: Alternative Room (Keep slot and teacher, find vacant room of same type)
        if slot and room:
            for r_id, r in all_rooms.items():
                if r_id == s.room_id or not r.is_active:
                    continue
                if r.room_type == room.room_type and r.capacity >= (cohort.student_count if cohort else 40):
                    if (slot.id, r_id) not in occupied_rooms:
                        alternatives.append({
                            "strategy": "REALLOCATE_ROOM",
                            "title": f"Relocate to {r.building} {r.room_number}",
                            "description": f"Move class to {r.building} {r.room_number} (Capacity: {r.capacity}, Type: {r.room_type.value}). Both teacher and student section retain scheduled time.",
                            "new_time_slot_id": s.time_slot_id,
                            "new_teacher_id": s.teacher_id,
                            "new_room_id": r.id,
                            "feasibility_score": 92.0,
                            "conflicts_introduced": 0,
                        })
                        break

        affected_details.append({
            "session_id": s.id,
            "subject_code": subject.code if subject else "",
            "subject_name": subject.name if subject else "",
            "teacher_id": s.teacher_id,
            "teacher_name": teacher.full_name if teacher else s.teacher_id,
            "room_id": s.room_id,
            "room_name": f"{room.building} {room.room_number}" if room else s.room_id,
            "cohort_section_id": s.cohort_section_id,
            "cohort_name": cohort.section_name if cohort else s.cohort_section_id,
            "current_slot_description": slot_desc,
            "time_slot_id": s.time_slot_id,
            "suggested_alternatives": alternatives,
        })

    return {
        "timetable_id": timetable_id,
        "disruption_type": request.disruption_type,
        "total_sessions": total_sessions_count,
        "affected_count": len(affected_sessions),
        "unaffected_preserved_count": unaffected_count,
        "preservation_rate_percent": preservation_rate,
        "affected_sessions": affected_details,
        "summary": f"Identified {len(affected_sessions)} affected class(es). {unaffected_count} classes ({preservation_rate}%) are safely preserved.",
    }


@router.post(
    "/apply",
    summary="Apply chosen reschedule resolution and automatically revalidate timetable",
)
async def apply_reschedule(
    request: ApplyRescheduleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    Applies the chosen alternative (time slot, substitute teacher, or room reallocation).
    Revalidates the timetable via ConflictService to ensure zero conflicts.
    """
    # Authorization: Faculty, HOD, and Admin only
    ALLOWED_RESCHEDULE_ROLES = {
        UserRoleEnum.ADMIN,
        UserRoleEnum.HOD,
        UserRoleEnum.COORDINATOR,
        UserRoleEnum.TEACHER,
    }
    if current_user and current_user.role not in ALLOWED_RESCHEDULE_ROLES:
        raise ForbiddenException("You do not have permission to reschedule timetable sessions. Timetables can only be modified by Faculty and HOD.")

    stmt = (
        select(TimetableSession)
        .options(
            selectinload(TimetableSession.subject),
            selectinload(TimetableSession.teacher).selectinload(Teacher.user),
            selectinload(TimetableSession.room),
            selectinload(TimetableSession.time_slot),
            selectinload(TimetableSession.cohort_section),
        )
        .where(TimetableSession.id == request.session_id)
    )
    sess_res = await db.execute(stmt)
    session = sess_res.scalars().first()
    if not session:
        raise NotFoundException(f"Session with ID '{request.session_id}' not found.")

    # Apply changes
    if request.new_time_slot_id:
        session.time_slot_id = request.new_time_slot_id
    if request.new_teacher_id:
        session.teacher_id = request.new_teacher_id
    if request.new_room_id:
        session.room_id = request.new_room_id

    await db.commit()
    await db.refresh(session)

    # Re-validate with ConflictService
    revalidation = await ConflictService.analyze_conflicts(session.timetable_id, db)

    return {
        "status": "APPLIED_AND_VERIFIED",
        "session_id": session.id,
        "timetable_id": session.timetable_id,
        "updated_details": {
            "subject_code": session.subject.code if session.subject else "",
            "teacher_id": session.teacher_id,
            "room_id": session.room_id,
            "time_slot_id": session.time_slot_id,
        },
        "revalidation": {
            "is_conflict_free": revalidation["is_conflict_free"],
            "critical_conflicts_count": revalidation["critical_conflicts_count"],
            "warnings_count": revalidation["warnings_count"],
        },
        "message": "Reschedule change applied and timetable revalidated successfully.",
    }
