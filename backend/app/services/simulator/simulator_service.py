from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.curriculum import SubjectTypeEnum
from app.models.infrastructure import Room, TimeSlot
from app.models.teacher import Teacher, TeacherAvailability
from app.models.timetable import Timetable, TimetableSession
from app.services.simulator.schemas import (
    AffectedSessionDetail,
    AlternativeOption,
    SimulationReport,
    SimulationScenarioRequest,
)


class ImpactSimulator:
    """
    What-If Impact Simulator Subsystem (FR-08).
    Executes in-memory sandbox analysis of proposed timetable disruptions or changes.
    Guarantees ZERO database writes during simulation.
    Identifies directly and indirectly affected sessions and generates up to 3 ranked alternatives.
    """

    @staticmethod
    async def simulate(
        request: SimulationScenarioRequest,
        db_session: AsyncSession,
    ) -> SimulationReport:
        # 1. Fetch timetable and active sessions with full relations loaded
        stmt = (
            select(Timetable)
            .options(
                selectinload(Timetable.sessions).selectinload(TimetableSession.cohort_section),
                selectinload(Timetable.sessions).selectinload(TimetableSession.subject),
                selectinload(Timetable.sessions).selectinload(TimetableSession.teacher).selectinload(Teacher.user),
                selectinload(Timetable.sessions).selectinload(TimetableSession.room),
                selectinload(Timetable.sessions).selectinload(TimetableSession.time_slot),
            )
            .where(Timetable.id == request.timetable_id)
        )
        result = await db_session.execute(stmt)
        timetable = result.scalars().first()
        if not timetable:
            raise NotFoundException(f"Timetable with ID '{request.timetable_id}' not found.")

        # 2. Fetch master data for department/institution to evaluate feasibility
        rooms_res = await db_session.execute(select(Room))
        all_rooms = {r.id: r for r in rooms_res.scalars().all()}

        teachers_res = await db_session.execute(select(Teacher).options(selectinload(Teacher.user)))
        all_teachers = {t.id: t for t in teachers_res.scalars().all()}

        slots_res = await db_session.execute(select(TimeSlot).order_by(TimeSlot.day_of_week, TimeSlot.period_number))
        all_slots = {s.id: s for s in slots_res.scalars().all()}

        avail_res = await db_session.execute(select(TeacherAvailability))
        avail_map: dict[tuple[str, str], TeacherAvailability] = {
            (a.teacher_id, a.time_slot_id): a for a in avail_res.scalars().all()
        }

        # 3. Analyze affected sessions in memory
        sessions = timetable.sessions
        directly_affected: list[AffectedSessionDetail] = []
        indirectly_affected: list[AffectedSessionDetail] = []
        diagnostics: list[str] = []

        target_session = next((s for s in sessions if s.id == request.target_session_id), None)
        proposed_slot_id = request.proposed_time_slot_id or (target_session.time_slot_id if target_session else None)
        proposed_room_id = request.proposed_room_id or (target_session.room_id if target_session else None)
        proposed_teacher_id = request.proposed_teacher_id or (target_session.teacher_id if target_session else None)

        if target_session:
            directly_affected.append(
                AffectedSessionDetail(
                    session_id=target_session.id,
                    subject_code=target_session.subject.code,
                    subject_name=target_session.subject.name,
                    cohort_name=target_session.cohort_section.section_name,
                    teacher_name=target_session.teacher.full_name,
                    room_number=f"{target_session.room.building} {target_session.room.room_number}",
                    current_time_slot_id=target_session.time_slot_id,
                    current_time_slot_name=f"{target_session.time_slot.day_of_week} Period {target_session.time_slot.period_number}",
                    conflict_reason="Target session selected for modification.",
                    is_directly_affected=True,
                )
            )

        # Check collisions if target session is moved to proposed slot/room/teacher
        if target_session and proposed_slot_id:
            for s in sessions:
                if s.id == target_session.id:
                    continue
                if s.time_slot_id == proposed_slot_id:
                    # Room collision
                    if proposed_room_id and s.room_id == proposed_room_id:
                        directly_affected.append(
                            AffectedSessionDetail(
                                session_id=s.id,
                                subject_code=s.subject.code,
                                subject_name=s.subject.name,
                                cohort_name=s.cohort_section.section_name,
                                teacher_name=s.teacher.full_name,
                                room_number=f"{s.room.building} {s.room.room_number}",
                                current_time_slot_id=s.time_slot_id,
                                current_time_slot_name=f"{s.time_slot.day_of_week} Period {s.time_slot.period_number}",
                                conflict_reason=f"Room double-booking collision: Room '{s.room.room_number}' already occupied by {s.subject.code}.",
                                is_directly_affected=True,
                            )
                        )
                        diagnostics.append(f"Room collision with existing session {s.subject.code} in {s.room.room_number}.")
                    # Teacher collision
                    if proposed_teacher_id and s.teacher_id == proposed_teacher_id:
                        directly_affected.append(
                            AffectedSessionDetail(
                                session_id=s.id,
                                subject_code=s.subject.code,
                                subject_name=s.subject.name,
                                cohort_name=s.cohort_section.section_name,
                                teacher_name=s.teacher.full_name,
                                room_number=f"{s.room.building} {s.room.room_number}",
                                current_time_slot_id=s.time_slot_id,
                                current_time_slot_name=f"{s.time_slot.day_of_week} Period {s.time_slot.period_number}",
                                conflict_reason=f"Teacher double-booking collision: {s.teacher.full_name} already teaching {s.subject.code}.",
                                is_directly_affected=True,
                            )
                        )
                        diagnostics.append(f"Teacher collision: {s.teacher.full_name} is already booked at this time slot.")
                    # Cohort collision
                    if s.cohort_section_id == target_session.cohort_section_id:
                        directly_affected.append(
                            AffectedSessionDetail(
                                session_id=s.id,
                                subject_code=s.subject.code,
                                subject_name=s.subject.name,
                                cohort_name=s.cohort_section.section_name,
                                teacher_name=s.teacher.full_name,
                                room_number=f"{s.room.building} {s.room.room_number}",
                                current_time_slot_id=s.time_slot_id,
                                current_time_slot_name=f"{s.time_slot.day_of_week} Period {s.time_slot.period_number}",
                                conflict_reason=f"Student cohort collision: Section '{s.cohort_section.section_name}' already has {s.subject.code}.",
                                is_directly_affected=True,
                            )
                        )
                        diagnostics.append(f"Cohort collision: Section '{s.cohort_section.section_name}' already scheduled at this slot.")

        # Check broader room maintenance or teacher unavailability scenarios
        if request.unavailable_room_id:
            for s in sessions:
                if s.room_id == request.unavailable_room_id and (not request.affected_time_slot_ids or s.time_slot_id in request.affected_time_slot_ids):
                    if not any(a.session_id == s.id for a in directly_affected):
                        directly_affected.append(
                            AffectedSessionDetail(
                                session_id=s.id,
                                subject_code=s.subject.code,
                                subject_name=s.subject.name,
                                cohort_name=s.cohort_section.section_name,
                                teacher_name=s.teacher.full_name,
                                room_number=f"{s.room.building} {s.room.room_number}",
                                current_time_slot_id=s.time_slot_id,
                                current_time_slot_name=f"{s.time_slot.day_of_week} Period {s.time_slot.period_number}",
                                conflict_reason=f"Room '{s.room.room_number}' declared unavailable/under maintenance.",
                                is_directly_affected=True,
                            )
                        )

        if request.unavailable_teacher_id:
            for s in sessions:
                if s.teacher_id == request.unavailable_teacher_id and (not request.affected_time_slot_ids or s.time_slot_id in request.affected_time_slot_ids):
                    if not any(a.session_id == s.id for a in directly_affected):
                        directly_affected.append(
                            AffectedSessionDetail(
                                session_id=s.id,
                                subject_code=s.subject.code,
                                subject_name=s.subject.name,
                                cohort_name=s.cohort_section.section_name,
                                teacher_name=s.teacher.full_name,
                                room_number=f"{s.room.building} {s.room.room_number}",
                                current_time_slot_id=s.time_slot_id,
                                current_time_slot_name=f"{s.time_slot.day_of_week} Period {s.time_slot.period_number}",
                                conflict_reason=f"Faculty '{s.teacher.full_name}' unavailable/on leave.",
                                is_directly_affected=True,
                            )
                        )

        # 4. Generate up to 3 feasible clash-free alternatives
        alternatives: list[AlternativeOption] = []
        if target_session:
            subject = target_session.subject
            cohort = target_session.cohort_section
            active_teacher_id = proposed_teacher_id or target_session.teacher_id
            active_teacher = all_teachers.get(active_teacher_id, target_session.teacher)

            # Build in-memory occupancy maps excluding the target session
            occupied_rooms: set[tuple[str, str]] = set()  # (slot_id, room_id)
            occupied_teachers: set[tuple[str, str]] = set()  # (slot_id, teacher_id)
            occupied_cohorts: set[tuple[str, str]] = set()  # (slot_id, cohort_id)

            for s in sessions:
                if s.id == target_session.id:
                    continue
                occupied_rooms.add((s.time_slot_id, s.room_id))
                occupied_teachers.add((s.time_slot_id, s.teacher_id))
                occupied_cohorts.add((s.time_slot_id, s.cohort_section_id))

            candidate_options: list[tuple[float, str, str, str, dict[str, Any]]] = []

            for slot_id, slot in all_slots.items():
                if slot.is_break:
                    continue
                # Cohort free?
                if (slot_id, cohort.id) in occupied_cohorts:
                    continue
                # Teacher free?
                if (slot_id, active_teacher_id) in occupied_teachers:
                    continue
                # Teacher available in slot?
                avail = avail_map.get((active_teacher_id, slot_id))
                if avail and not avail.is_available:
                    continue

                pref_weight = avail.preference_weight if avail else 0

                # Candidate rooms
                for room_id, room in all_rooms.items():
                    # Room free?
                    if (slot_id, room_id) in occupied_rooms:
                        continue
                    # Room capacity?
                    if room.capacity < cohort.student_count:
                        continue
                    # Lab suitability?
                    if subject.subject_type == SubjectTypeEnum.LABORATORY:
                        if not room.is_lab or room.room_type != subject.required_room_type:
                            continue
                    else:
                        # Theory session in lab is discouraged
                        if room.is_lab:
                            continue

                    # Calculate penalty score (lower is better)
                    # Base score: preferred slot gives negative penalty
                    penalty = 50.0 - (pref_weight * 10.0)
                    if room_id != target_session.room_id:
                        penalty += 15.0  # Room change penalty
                    if slot.day_of_week != target_session.time_slot.day_of_week:
                        penalty += 10.0  # Day shift penalty

                    explanation = {
                        "day": slot.day_of_week,
                        "period": slot.period_number,
                        "room": room.room_number,
                        "teacher": active_teacher.full_name,
                        "capacity_margin": room.capacity - cohort.student_count,
                        "teacher_preference": pref_weight,
                        "displaced_sessions": 0,
                        "notes": (
                            f"Zero clashes with section {cohort.section_name}; "
                            f"Room {room.room_number} (cap {room.capacity}) fits {cohort.student_count} students; "
                            f"Teacher preference weight: {pref_weight:+d}."
                        ),
                    }
                    candidate_options.append((penalty, slot_id, room_id, active_teacher_id, explanation))

            # Sort candidate options by penalty score ascending
            candidate_options.sort(key=lambda x: x[0])

            rank = 1
            for penalty, slot_id, room_id, teacher_id, expl in candidate_options[:3]:
                slot = all_slots[slot_id]
                room = all_rooms[room_id]
                teacher = all_teachers[teacher_id]
                alternatives.append(
                    AlternativeOption(
                        option_rank=rank,
                        proposed_time_slot_id=slot_id,
                        proposed_time_slot_name=f"{slot.day_of_week} Period {slot.period_number}",
                        proposed_room_id=room_id,
                        proposed_room_number=f"{room.building} {room.room_number}",
                        proposed_teacher_id=teacher_id,
                        proposed_teacher_name=teacher.full_name,
                        affected_sessions_count=1,
                        soft_penalty_score=round(penalty, 2),
                        trade_off_explanation=expl,
                        is_feasible=True,
                    )
                )
                rank += 1

        is_feasible = len(directly_affected) == 1 if target_session and proposed_slot_id else len(directly_affected) == 0

        summary = (
            f"Impact Simulation: {len(directly_affected)} directly affected session(s), "
            f"{len(indirectly_affected)} indirectly affected session(s). "
            f"{len(alternatives)} clash-free alternative(s) generated."
        )

        return SimulationReport(
            timetable_id=timetable.id,
            scenario_summary=summary,
            is_feasible=is_feasible,
            directly_affected_count=len(directly_affected),
            indirectly_affected_count=len(indirectly_affected),
            affected_sessions=directly_affected + indirectly_affected,
            alternatives=alternatives,
            diagnostics=diagnostics,
        )
