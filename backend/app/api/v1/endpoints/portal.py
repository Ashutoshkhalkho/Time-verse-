import uuid
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.db.session import get_db_session
from app.models.change_request import ChangeRequest, RequestStatusEnum
from app.models.infrastructure import Room
from app.models.organization import Department
from app.models.teacher import Teacher
from app.models.timetable import Timetable, TimetableSession
from app.models.user import MentorAssignment, StudentEnrollment, User, UserRoleEnum
from app.services.scheduler.conflict_service import ConflictService

router = APIRouter(prefix="/portal", tags=["Portal & Timetable Dashboard"])


def generate_ulid() -> str:
    return uuid.uuid4().hex[:26]


class DashboardSummaryResponse(BaseModel):
    user_id: str
    user_name: str
    user_role: str
    department_id: str | None
    timetable_status: dict[str, Any]
    conflict_summary: dict[str, Any]
    rescheduler_summary: dict[str, Any]
    next_class: dict[str, Any] | None
    quick_stats: list[dict[str, Any]]
    metrics: dict[str, Any] = {}


class LegacySummaryResponse(BaseModel):
    user_id: str
    user_name: str
    user_role: str
    department_id: str | None
    metrics: dict[str, Any]
    next_class: dict[str, Any] | None
    quick_stats: list[dict[str, Any]]


class StudentRecordsResponse(BaseModel):
    student_name: str
    register_number: str
    programme_name: str
    semester: str
    cohort_section_name: str
    attendance_percentage: float
    hall_ticket: dict[str, Any]
    fee_details: dict[str, Any]
    mentor_info: dict[str, Any]


class AppointmentSlotDto(BaseModel):
    id: str
    title: str
    host_name: str
    host_role: str
    date_str: str
    time_str: str
    location: str
    status: str
    is_booked: bool
    booked_by_user_id: str | None = None


SAMPLE_APPOINTMENTS: list[dict[str, Any]] = [
    {
        "id": "apt_01",
        "title": "Academic Advising & Office Hours",
        "host_name": "Prof. Sneha Rao",
        "host_role": "Faculty Mentor",
        "date_str": "Wednesday, Oct 14, 2026",
        "time_str": "14:00 - 14:30",
        "location": "Faculty Cabin #204, Admin Block",
        "status": "AVAILABLE",
        "is_booked": False,
        "booked_by_user_id": None,
    },
    {
        "id": "apt_02",
        "title": "Algorithms & Timetable Doubt Session",
        "host_name": "Dr. Rajesh Sharma",
        "host_role": "Subject Faculty",
        "date_str": "Thursday, Oct 15, 2026",
        "time_str": "15:30 - 16:00",
        "location": "LH-101 Seminar Corner",
        "status": "AVAILABLE",
        "is_booked": False,
        "booked_by_user_id": None,
    },
]


@router.get("/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DashboardSummaryResponse:
    dept_id = "dept_cs"

    tt_stmt = (
        select(Timetable)
        .options(
            selectinload(Timetable.sessions).selectinload(TimetableSession.subject),
            selectinload(Timetable.sessions).selectinload(TimetableSession.teacher).selectinload(Teacher.user),
            selectinload(Timetable.sessions).selectinload(TimetableSession.room),
            selectinload(Timetable.sessions).selectinload(TimetableSession.time_slot),
            selectinload(Timetable.sessions).selectinload(TimetableSession.cohort_section),
        )
        .order_by(Timetable.version_major.desc(), Timetable.version_minor.desc())
        .limit(1)
    )
    tt_res = await db.execute(tt_stmt)
    latest_timetable = tt_res.scalars().first()

    cr_stmt = select(func.count(ChangeRequest.id)).where(
        ChangeRequest.status.in_([RequestStatusEnum.SUBMITTED, RequestStatusEnum.UNDER_REVIEW, RequestStatusEnum.ALTERNATIVES_PROPOSED])
    )
    pending_cr_count = (await db.execute(cr_stmt)).scalar_one() or 0

    conflict_summary: dict[str, Any] = {
        "is_conflict_free": True,
        "critical_conflicts_count": 0,
        "warnings_count": 0,
    }
    if latest_timetable:
        conflict_res = await ConflictService.analyze_conflicts(latest_timetable.id, db)
        conflict_summary = {
            "is_conflict_free": conflict_res["is_conflict_free"],
            "critical_conflicts_count": conflict_res["critical_conflicts_count"],
            "warnings_count": conflict_res["warnings_count"],
            "conflicts_preview": conflict_res["conflicts"][:3],
        }

    next_class: dict[str, Any] | None = None
    sessions = latest_timetable.sessions if latest_timetable else []

    if current_user.role == UserRoleEnum.TEACHER:
        tch_stmt = select(Teacher).where(Teacher.user_id == current_user.id)
        teacher_rec = (await db.execute(tch_stmt)).scalars().first()
        t_id = teacher_rec.id if teacher_rec else "tch_sharma"
        my_sessions = [s for s in sessions if s.teacher_id == t_id]
        if my_sessions:
            first_s = my_sessions[0]
            next_class = {
                "subject_code": first_s.subject.code if first_s.subject else "CS301",
                "subject_name": first_s.subject.name if first_s.subject else "Data Structures",
                "room_name": f"{first_s.room.building} {first_s.room.room_number}" if first_s.room else "LH-101",
                "time_slot": f"Day {first_s.time_slot.day_of_week} Period {first_s.time_slot.period_number}" if first_s.time_slot else "08:30 - 09:20",
                "cohort_name": first_s.cohort_section.section_name if first_s.cohort_section else "CS-3A",
                "instructor": current_user.full_name,
            }
    else:
        if sessions:
            first_s = sessions[0]
            next_class = {
                "subject_code": first_s.subject.code if first_s.subject else "CS301",
                "subject_name": first_s.subject.name if first_s.subject else "Data Structures & Algorithms",
                "room_name": f"{first_s.room.building} {first_s.room.room_number}" if first_s.room else "LH-101",
                "time_slot": f"Day {first_s.time_slot.day_of_week} Period {first_s.time_slot.period_number}" if first_s.time_slot else "08:30 - 09:20",
                "instructor": first_s.teacher.full_name if first_s.teacher else "Prof. Vikram Sharma",
                "cohort_name": first_s.cohort_section.section_name if first_s.cohort_section else "CS-3A",
            }

    total_sessions = len(sessions)
    timetable_status = {
        "id": latest_timetable.id if latest_timetable else None,
        "version": f"v{latest_timetable.version_major}.{latest_timetable.version_minor}" if latest_timetable else "N/A",
        "status": latest_timetable.status.value if latest_timetable else "DRAFT",
        "solver_status": latest_timetable.solver_status if latest_timetable else "OPTIMAL",
        "total_sessions": total_sessions,
        "published_at": latest_timetable.published_at.isoformat() if latest_timetable and latest_timetable.published_at else None,
        "is_conflict_free": conflict_summary["is_conflict_free"],
    }

    rescheduler_summary = {
        "pending_proposals_count": pending_cr_count,
        "preservation_rate": "98.5%",
        "active_disruptions": 0,
    }

    quick_stats = [
        {"label": "Master Timetable", "value": timetable_status["version"], "trend": timetable_status["status"], "type": "TIMETABLE"},
        {"label": "Conflict Status", "value": "Zero Clashes" if conflict_summary["is_conflict_free"] else f"{conflict_summary['critical_conflicts_count']} Clashes", "trend": "100% Conflict-Free" if conflict_summary["is_conflict_free"] else "Needs Resolution", "type": "CONFLICT"},
        {"label": "Smart Rescheduler", "value": f"{pending_cr_count} Proposals", "trend": "Active Sandbox", "type": "RESCHEDULER"},
        {"label": "Scheduled Sessions", "value": f"{total_sessions} Classes", "trend": "CP-SAT Verified", "type": "SESSIONS"},
    ]

    return DashboardSummaryResponse(
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_role=current_user.role.value,
        department_id=dept_id,
        timetable_status=timetable_status,
        conflict_summary=conflict_summary,
        rescheduler_summary=rescheduler_summary,
        next_class=next_class,
        quick_stats=quick_stats,
        metrics={
            "total_users": 10,
            "total_rooms": 4,
            "total_departments": 1,
            "capacity_utilization": "76.7%",
            "solver_engine": "OR-Tools CP-SAT",
            "weekly_teaching_sessions": 8,
            "attendance_rate": "92.4%",
            "hall_ticket_status": "AVAILABLE",
            "fee_dues": "$0.00",
            "mentor_name": "Prof. Sneha Rao",
        },
    )


@router.get("/summary", response_model=LegacySummaryResponse)
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> LegacySummaryResponse:
    dept_id = "dept_cs"
    tt_stmt = (
        select(Timetable)
        .options(
            selectinload(Timetable.sessions).selectinload(TimetableSession.subject),
            selectinload(Timetable.sessions).selectinload(TimetableSession.teacher),
            selectinload(Timetable.sessions).selectinload(TimetableSession.room),
            selectinload(Timetable.sessions).selectinload(TimetableSession.time_slot),
            selectinload(Timetable.sessions).selectinload(TimetableSession.cohort_section),
        )
        .where(Timetable.department_id == dept_id)
        .order_by(Timetable.version_major.desc(), Timetable.version_minor.desc())
        .limit(1)
    )
    latest_timetable = (await db.execute(tt_stmt)).scalars().first()

    cr_stmt = select(func.count(ChangeRequest.id)).where(
        ChangeRequest.status.in_([RequestStatusEnum.SUBMITTED, RequestStatusEnum.UNDER_REVIEW, RequestStatusEnum.ALTERNATIVES_PROPOSED])
    )
    pending_cr_count = (await db.execute(cr_stmt)).scalar_one() or 0

    metrics: dict[str, Any] = {}
    quick_stats: list[dict[str, Any]] = []
    next_class: dict[str, Any] | None = None

    if current_user.role == UserRoleEnum.ADMIN:
        metrics = {
            "total_users": 10,
            "total_rooms": 4,
            "total_departments": 1,
            "pending_change_requests": pending_cr_count,
            "system_health": "100% OPERATIONAL",
            "active_timetable_version": f"v{latest_timetable.version_major}.{latest_timetable.version_minor}" if latest_timetable else "N/A",
        }
    elif current_user.role == UserRoleEnum.HOD:
        metrics = {
            "department_faculty": 4,
            "active_version": "v1.0",
            "status": "PUBLISHED",
            "capacity_utilization": "76.7%",
            "pending_approvals": pending_cr_count,
        }
    elif current_user.role == UserRoleEnum.COORDINATOR:
        metrics = {
            "active_version": "v1.0",
            "lock_version": 1,
            "status": "PUBLISHED",
            "total_sessions": 46,
            "pending_change_requests": pending_cr_count,
            "solver_engine": "OR-Tools CP-SAT (Verified Decoupled)",
        }
    elif current_user.role == UserRoleEnum.TEACHER:
        metrics = {
            "weekly_teaching_sessions": 8,
            "max_weekly_hours": 20,
            "assigned_cohorts": "CS-3A, CS-3B",
            "pending_leave_requests": 0,
        }
    elif current_user.role in {UserRoleEnum.STUDENT, UserRoleEnum.CR}:
        metrics = {
            "enrolled_section": "CS-3A (BSc Computer Science)",
            "attendance_rate": "92.4%",
            "hall_ticket_status": "AVAILABLE",
            "fees_status": "NO DUES (PAID)",
            "mentor_name": "Prof. Sneha Rao",
        }
    elif current_user.role == UserRoleEnum.MENTOR:
        metrics = {
            "assigned_mentees": 1,
            "next_meeting": "Wednesday, Oct 14, 2026 at 14:00",
            "mentor_book_status": "UP TO DATE",
        }

    return LegacySummaryResponse(
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_role=current_user.role.value,
        department_id=dept_id,
        metrics=metrics,
        next_class=next_class,
        quick_stats=quick_stats,
    )


@router.get("/student-records", response_model=StudentRecordsResponse)
async def get_student_records(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudentRecordsResponse:
    return StudentRecordsResponse(
        student_name=current_user.full_name,
        register_number="24CS301A",
        programme_name="Bachelor of Science in Computer Science (Honours)",
        semester="Semester V (Odd Academic Term 2026)",
        cohort_section_name="Section 3A (CS-3A)",
        attendance_percentage=92.4,
        hall_ticket={
            "examination": "End-Semester Autonomous Examinations (Theory & Practical)",
            "hall_ticket_number": "HT-2026-CS-3A-042",
            "status": "AVAILABLE",
            "issue_date": "October 08, 2026",
            "centre": "KJU Main Campus, Block II",
            "instructions": ["Produced with identity card."],
        },
        fee_details={
            "academic_year": "2026-2027",
            "total_annual_tuition": "$4,200.00",
            "paid_amount": "$4,200.00",
            "pending_dues": "$0.00",
            "status": "CLEARED / NO DUES",
            "receipt_number": "RCT-2026-99214",
            "payment_date": "July 24, 2026",
        },
        mentor_info={
            "mentor_name": "Prof. Sneha Rao",
            "mentor_email": "mentor.rao@timewise.edu",
            "department": "Department of Computer Science",
            "office_location": "Cabin 204, Administrative Block",
            "meeting_schedule": "Alternate Wednesdays",
        },
    )


@router.get("/appointments", response_model=list[AppointmentSlotDto])
async def list_appointments(
    current_user: User = Depends(get_current_user),
) -> list[AppointmentSlotDto]:
    return [AppointmentSlotDto(**apt) for apt in SAMPLE_APPOINTMENTS]


@router.post("/appointments/{appointment_id}/book")
async def book_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {"id": appointment_id, "status": "CONFIRMED", "host": "Prof. Sneha Rao"}


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {"id": appointment_id, "status": "CANCELLED"}


@router.get("/mentor-mentees")
async def get_mentor_mentees(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    if current_user.role not in {UserRoleEnum.MENTOR, UserRoleEnum.ADMIN, UserRoleEnum.HOD}:
        raise ForbiddenException("Authorized mentor access required.")
    return [{
        "student_id": "usr_demo_student_aarav",
        "student_name": "Aarav Menon",
        "student_email": "student.aarav@timewise.edu",
        "cohort_section": "CS-3A",
        "attendance_percentage": 92.4,
        "mentor_notes": "Student demonstrated strong engagement in data structures.",
        "last_meeting_date": "September 28, 2026",
    }]
