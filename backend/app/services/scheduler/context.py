from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cohort import CohortSection
from app.models.curriculum import SubjectRequirement
from app.models.infrastructure import Room, TimeSlot
from app.models.teacher import Teacher
from app.services.scheduler.schemas import (
    CohortSectionInput,
    RoomScheduleInput,
    SubjectRequirementInput,
    TeacherScheduleInput,
    TimeSlotInput,
)


async def load_scheduling_context(
    department_id: str,
    academic_term_id: str,
    db: AsyncSession,
) -> tuple[
    list[TeacherScheduleInput],
    list[RoomScheduleInput],
    list[TimeSlotInput],
    list[CohortSectionInput],
    list[SubjectRequirementInput],
]:
    """Loads validated schedule input objects from database for a given department and academic term."""
    # 1. Slots
    slot_stmt = select(TimeSlot).order_by(TimeSlot.day_of_week, TimeSlot.period_number)
    slots_db = (await db.execute(slot_stmt)).scalars().all()
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

    # 2. Rooms
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

    # 3. Teachers with availability
    teacher_stmt = (
        select(Teacher)
        .options(selectinload(Teacher.availabilities), selectinload(Teacher.user))
        .where(Teacher.department_id == department_id)
    )
    teachers_db = (await db.execute(teacher_stmt)).scalars().all()
    teachers_input = [
        TeacherScheduleInput(
            id=t.id,
            name=t.full_name,
            max_hours_per_day=t.max_hours_per_day,
            max_consecutive_hours=t.max_consecutive_hours,
            max_weekly_hours=t.max_weekly_hours,
            unavailable_slot_ids=frozenset(
                a.time_slot_id for a in t.availabilities if not a.is_available
            ),
            preference_weights={
                a.time_slot_id: a.preference_weight
                for a in t.availabilities
                if a.preference_weight != 0
            },
        )
        for t in teachers_db
    ]

    # 4. Cohorts
    cohort_stmt = select(CohortSection).where(
        CohortSection.department_id == department_id,
        CohortSection.academic_term_id == academic_term_id,
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

    # 5. Requirements
    cohort_ids = [c.id for c in cohorts_db]
    if cohort_ids:
        req_stmt = (
            select(SubjectRequirement)
            .options(selectinload(SubjectRequirement.subject))
            .where(SubjectRequirement.cohort_section_id.in_(cohort_ids))
        )
        reqs_db = (await db.execute(req_stmt)).scalars().all()
    else:
        reqs_db = []

    requirements_input = [
        SubjectRequirementInput(
            id=r.id,
            cohort_section_id=r.cohort_section_id,
            subject_id=r.subject_id,
            subject_code=r.subject.code,
            subject_name=r.subject.name,
            subject_type=r.subject.subject_type.value,
            teacher_id=r.teacher_id,
            required_room_type=r.subject.required_room_type.value,
            required_sessions_per_week=r.required_sessions_per_week,
            duration_periods=r.duration_periods,
            requires_consecutive_periods=r.requires_consecutive_periods,
            preferred_room_id=r.preferred_room_id,
        )
        for r in reqs_db
    ]

    return teachers_input, rooms_input, slots_input, cohorts_input, requirements_input
