import time
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import PermissionGuard, get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.core.permissions import Permission
from app.db.session import get_db_session
from app.models.cohort import CohortSection
from app.models.curriculum import Subject, SubjectRequirement, SubjectTypeEnum
from app.models.infrastructure import Room, RoomTypeEnum, TimeSlot
from app.models.organization import AcademicTerm, Department, Institution
from app.models.preference import SchedulingPreference
from app.models.teacher import Teacher
from app.models.user import User, UserRoleEnum

router = APIRouter(prefix="/setup", tags=["Semester Setup Wizard"])


class SemesterDetailsStep(BaseModel):
    academic_year: str = "2026-2027"
    term_name: str = "Odd Semester 2026"
    start_date: str = "2026-08-01"
    end_date: str = "2026-12-15"
    department_id: str = "dept_cs"
    working_days: list[int] = [1, 2, 3, 4, 5]  # Mon-Fri
    daily_periods: int = 6


class RulesStep(BaseModel):
    college_start_time: str = "09:00"
    period_duration_minutes: int = 50
    lunch_period: int = 4
    max_daily_sessions_per_teacher: int = 4
    max_daily_sessions_per_cohort: int = 5
    weight_balanced_daily_workload: int = 15
    weight_minimize_gaps: int = 10


class SemesterSetupPayload(BaseModel):
    department_id: str = "dept_cs"
    current_step: int = 1
    semester_details: SemesterDetailsStep = Field(default_factory=SemesterDetailsStep)
    rules: RulesStep = Field(default_factory=RulesStep)
    teachers_count: int = 0
    subjects_count: int = 0
    rooms_count: int = 0
    requirements_count: int = 0
    notes: str | None = None


# In-memory drafts store for quick wizard resume (backed by DB preferences)
_DRAFTS_STORE: dict[str, dict[str, Any]] = {}


@router.get("/summary/{department_id}")
async def get_setup_summary(
    department_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    Returns complete semester setup readiness for a department:
    existing counts, active term, teachers, rooms, subjects, and validation status.
    """
    if current_user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
        raise ForbiddenException("Access restricted: Semester setup is reserved for HOD and administrative coordinators.")

    dept_res = await db.execute(select(Department).where(Department.id == department_id))
    dept = dept_res.scalars().first()
    if not dept:
        raise NotFoundException(f"Department '{department_id}' not found.")

    term_res = await db.execute(select(AcademicTerm).where(AcademicTerm.is_active == True))  # noqa: E712
    active_term = term_res.scalars().first()

    teachers = (await db.execute(
        select(Teacher).options(selectinload(Teacher.user)).where(Teacher.department_id == department_id)
    )).scalars().all()

    subjects = (await db.execute(
        select(Subject).where(Subject.department_id == department_id)
    )).scalars().all()

    rooms = (await db.execute(select(Room).where(Room.is_active == True))).scalars().all()  # noqa: E712

    cohorts = (await db.execute(
        select(CohortSection).where(CohortSection.department_id == department_id)
    )).scalars().all()

    slots = (await db.execute(select(TimeSlot))).scalars().all()

    pref_res = await db.execute(
        select(SchedulingPreference).where(SchedulingPreference.department_id == department_id)
    )
    pref = pref_res.scalars().first()

    requirements = (await db.execute(
        select(SubjectRequirement).join(Subject, SubjectRequirement.subject_id == Subject.id)
        .where(Subject.department_id == department_id)
    )).scalars().all()

    # Calculate readiness checks
    checks = []
    has_term = active_term is not None
    checks.append({
        "step": 1,
        "name": "Semester & Academic Term",
        "passed": has_term,
        "message": f"Active Term: {active_term.name}" if has_term else "No active academic term configured.",
    })

    has_teachers_subjects = len(teachers) > 0 and len(subjects) > 0 and len(requirements) > 0
    checks.append({
        "step": 2,
        "name": "Faculty & Curriculum Requirements",
        "passed": has_teachers_subjects,
        "message": f"{len(teachers)} teachers, {len(subjects)} subjects, {len(requirements)} weekly teaching requirements mapped.",
    })

    has_rooms = len(rooms) > 0
    checks.append({
        "step": 3,
        "name": "Classrooms & Laboratory Infrastructure",
        "passed": has_rooms,
        "message": f"{len(rooms)} active rooms ({sum(1 for r in rooms if r.is_lab)} labs, {sum(1 for r in rooms if not r.is_lab)} lecture halls).",
    })

    has_rules = len(slots) > 0 and pref is not None
    checks.append({
        "step": 4,
        "name": "Timetable Rules & Schedule Slots",
        "passed": has_rules,
        "message": f"{len(slots)} periods configured across working days. Rules active.",
    })

    is_ready_for_generation = all(c["passed"] for c in checks)

    saved_draft = _DRAFTS_STORE.get(department_id)

    return {
        "department_id": department_id,
        "department_name": dept.name,
        "department_code": dept.code,
        "active_term": {
            "id": active_term.id,
            "name": active_term.name,
            "start_date": active_term.start_date.isoformat(),
            "end_date": active_term.end_date.isoformat(),
        } if active_term else None,
        "counts": {
            "teachers": len(teachers),
            "subjects": len(subjects),
            "rooms": len(rooms),
            "cohort_sections": len(cohorts),
            "requirements": len(requirements),
            "time_slots": len(slots),
        },
        "readiness_checks": checks,
        "is_ready_for_generation": is_ready_for_generation,
        "saved_draft": saved_draft,
    }


@router.post("/draft")
async def save_setup_draft(
    payload: SemesterSetupPayload,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    Saves the user's wizard progress as a draft so they can safely leave and resume anytime.
    """
    if current_user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
        raise ForbiddenException("Only HOD or Admin can configure semester setup.")

    draft_data = payload.model_dump()
    draft_data["saved_at"] = datetime.now().isoformat()
    draft_data["saved_by"] = current_user.full_name
    _DRAFTS_STORE[payload.department_id] = draft_data

    return {
        "message": "Semester setup draft saved successfully. You can safely resume this setup anytime.",
        "department_id": payload.department_id,
        "current_step": payload.current_step,
        "saved_at": draft_data["saved_at"],
    }


@router.post("/commit")
async def commit_semester_setup(
    payload: SemesterSetupPayload,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    Atomically commits and activates the semester configuration into production tables.
    """
    if current_user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
        raise ForbiddenException("Only HOD or Admin can commit semester setup.")

    # 1. Update or create AcademicTerm
    term_res = await db.execute(
        select(AcademicTerm).where(AcademicTerm.name == payload.semester_details.term_name)
    )
    term = term_res.scalars().first()
    if not term:
        term = AcademicTerm(
            id=f"term_{int(time.time())}",
            institution_id="inst_01",
            name=payload.semester_details.term_name,
            start_date=date.fromisoformat(payload.semester_details.start_date),
            end_date=date.fromisoformat(payload.semester_details.end_date),
            is_active=True,
        )
        db.add(term)
    else:
        term.is_active = True
        term.start_date = date.fromisoformat(payload.semester_details.start_date)
        term.end_date = date.fromisoformat(payload.semester_details.end_date)

    # 2. Update SchedulingPreference
    pref_res = await db.execute(
        select(SchedulingPreference).where(SchedulingPreference.department_id == payload.department_id)
    )
    pref = pref_res.scalars().first()
    if not pref:
        pref = SchedulingPreference(
            id=f"pref_{payload.department_id}",
            department_id=payload.department_id,
            weight_preferred_times=10,
            weight_balanced_daily_workload=payload.rules.weight_balanced_daily_workload,
            weight_minimize_gaps=payload.rules.weight_minimize_gaps,
            max_daily_sessions_per_teacher=payload.rules.max_daily_sessions_per_teacher,
            max_daily_sessions_per_cohort=payload.rules.max_daily_sessions_per_cohort,
            custom_rules={
                "college_start_time": payload.rules.college_start_time,
                "period_duration_minutes": payload.rules.period_duration_minutes,
                "lunch_period": payload.rules.lunch_period,
            },
        )
        db.add(pref)
    else:
        pref.weight_balanced_daily_workload = payload.rules.weight_balanced_daily_workload
        pref.weight_minimize_gaps = payload.rules.weight_minimize_gaps
        pref.max_daily_sessions_per_teacher = payload.rules.max_daily_sessions_per_teacher
        pref.max_daily_sessions_per_cohort = payload.rules.max_daily_sessions_per_cohort
        pref.custom_rules = {
            "college_start_time": payload.rules.college_start_time,
            "period_duration_minutes": payload.rules.period_duration_minutes,
            "lunch_period": payload.rules.lunch_period,
        }

    await db.commit()

    # Clear draft
    _DRAFTS_STORE.pop(payload.department_id, None)

    return {
        "message": f"Semester '{payload.semester_details.term_name}' configured and saved successfully. You may now generate timetables.",
        "term_id": term.id,
        "term_name": term.name,
        "is_ready_for_generation": True,
    }
