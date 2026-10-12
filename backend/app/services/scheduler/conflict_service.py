from collections import defaultdict
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.curriculum import SubjectRequirement
from app.models.infrastructure import Room, TimeSlot
from app.models.teacher import Teacher, TeacherAvailability
from app.models.timetable import Timetable, TimetableSession


class ConflictService:
    """
    Dedicated Conflict Detection and Analysis Service.
    Detects teacher double-bookings, classroom and lab clashes, student section overlaps,
    room capacity violations, and laboratory requirement violations.
    Provides structured conflict explanations and feasible resolution suggestions.
    Never reports a timetable as conflict-free when any hard constraint is violated.
    """

    @staticmethod
    async def analyze_conflicts(
        timetable_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        # 1. Fetch timetable and sessions
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
            return {
                "timetable_id": timetable_id,
                "is_conflict_free": False,
                "critical_conflicts_count": 0,
                "warnings_count": 0,
                "conflicts": [],
                "error": f"Timetable '{timetable_id}' not found.",
            }

        # 2. Master Data
        rooms_res = await db.execute(select(Room))
        all_rooms = {r.id: r for r in rooms_res.scalars().all()}

        teachers_res = await db.execute(select(Teacher).options(selectinload(Teacher.user)))
        all_teachers = {t.id: t for t in teachers_res.scalars().all()}

        slots_res = await db.execute(select(TimeSlot).order_by(TimeSlot.day_of_week, TimeSlot.period_number))
        all_slots = {s.id: s for s in slots_res.scalars().all()}

        avail_res = await db.execute(select(TeacherAvailability))
        unavail_slots_by_teacher = defaultdict(set)
        for a in avail_res.scalars().all():
            if not a.is_available:
                unavail_slots_by_teacher[a.teacher_id].add(a.time_slot_id)

        reqs_res = await db.execute(select(SubjectRequirement))
        all_reqs = {r.id: r for r in reqs_res.scalars().all()}

        sessions = timetable.sessions
        days_map = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}

        conflicts: list[dict[str, Any]] = []

        # Groupings
        teacher_slot_map = defaultdict(list)
        room_slot_map = defaultdict(list)
        cohort_slot_map = defaultdict(list)

        # Build occupancy maps for finding resolution alternatives
        occupied_rooms = set()
        occupied_teachers = set()
        occupied_cohorts = set()

        for s in sessions:
            if s.time_slot_id:
                occupied_rooms.add((s.time_slot_id, s.room_id))
                occupied_teachers.add((s.time_slot_id, s.teacher_id))
                occupied_cohorts.add((s.time_slot_id, s.cohort_section_id))

                teacher_slot_map[(s.teacher_id, s.time_slot_id)].append(s)
                room_slot_map[(s.room_id, s.time_slot_id)].append(s)
                cohort_slot_map[(s.cohort_section_id, s.time_slot_id)].append(s)

        # Helper to format session info
        def session_summary(s: TimetableSession) -> dict[str, Any]:
            slot_name = f"{days_map.get(s.time_slot.day_of_week if s.time_slot else 1, '')} P{s.time_slot.period_number if s.time_slot else ''}"
            teacher_name = s.teacher.full_name if s.teacher else (all_teachers.get(s.teacher_id).full_name if s.teacher_id in all_teachers else s.teacher_id)
            room_name = f"{s.room.building} {s.room.room_number}" if s.room else s.room_id
            return {
                "session_id": s.id,
                "subject_code": s.subject.code if s.subject else "",
                "subject_name": s.subject.name if s.subject else "",
                "teacher_id": s.teacher_id,
                "teacher_name": teacher_name,
                "room_id": s.room_id,
                "room_name": room_name,
                "cohort_section_id": s.cohort_section_id,
                "cohort_name": s.cohort_section.section_name if s.cohort_section else s.cohort_section_id,
                "time_slot_id": s.time_slot_id,
                "slot_description": slot_name,
            }

        # Helper to find free slot for a session
        def find_free_slot(s: TimetableSession) -> str | None:
            for sl_id, sl in all_slots.items():
                if sl.is_break or sl_id == s.time_slot_id:
                    continue
                if (sl_id, s.room_id) not in occupied_rooms and \
                   (sl_id, s.teacher_id) not in occupied_teachers and \
                   (sl_id, s.cohort_section_id) not in occupied_cohorts:
                    return f"{days_map.get(sl.day_of_week, 'Day')} Period {sl.period_number} ({sl.start_time.strftime('%H:%M')})"
            return None

        # Helper to find free room of suitable type
        def find_free_room(slot_id: str, required_type: str, min_cap: int) -> Room | None:
            for r_id, r in all_rooms.items():
                if r.is_active and r.room_type.value == required_type and r.capacity >= min_cap:
                    if (slot_id, r_id) not in occupied_rooms:
                        return r
            return None

        # 1. Teacher Double-Booking Check
        for (t_id, slot_id), conflicting_sessions in teacher_slot_map.items():
            if len(conflicting_sessions) > 1:
                t = all_teachers.get(t_id)
                teacher_name = t.full_name if t else t_id
                slot = all_slots.get(slot_id)
                day_name = days_map.get(slot.day_of_week if slot else 1, "Unknown Day")
                p_num = slot.period_number if slot else 0
                time_range = f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}" if slot and slot.start_time else ""

                suggestions = []
                free_slot = find_free_slot(conflicting_sessions[1])
                if free_slot:
                    suggestions.append(f"Shift '{conflicting_sessions[1].subject.code if conflicting_sessions[1].subject else 'Session'}' to {free_slot} where both teacher and section are free.")
                else:
                    suggestions.append("Reassign one of the overlapping sessions to another qualified department instructor.")

                conflicts.append({
                    "id": f"cnf_teacher_{t_id}_{slot_id}",
                    "type": "TEACHER_DOUBLE_BOOKING",
                    "severity": "CRITICAL",
                    "title": f"Teacher Double-Booking: {teacher_name}",
                    "description": f"Faculty {teacher_name} is simultaneously scheduled for {len(conflicting_sessions)} overlapping classes during {day_name} Period {p_num} ({time_range}).",
                    "day_number": slot.day_of_week if slot else 1,
                    "day_name": day_name,
                    "period_number": p_num,
                    "time_slot_id": slot_id,
                    "affected_classes": [session_summary(s) for s in conflicting_sessions],
                    "affected_resource_type": "TEACHER",
                    "affected_resource_name": teacher_name,
                    "feasible_resolutions": suggestions,
                })

        # 2. Room Double-Booking Check
        for (r_id, slot_id), conflicting_sessions in room_slot_map.items():
            if len(conflicting_sessions) > 1:
                r = all_rooms.get(r_id)
                room_name = f"{r.building} {r.room_number}" if r else r_id
                slot = all_slots.get(slot_id)
                day_name = days_map.get(slot.day_of_week if slot else 1, "Unknown Day")
                p_num = slot.period_number if slot else 0
                time_range = f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}" if slot and slot.start_time else ""

                suggestions = []
                free_room = find_free_room(slot_id, r.room_type.value if r else "LECTURE_HALL", 40)
                if free_room:
                    suggestions.append(f"Relocate one session to {free_room.building} {free_room.room_number} (Capacity: {free_room.capacity}), which is completely vacant at this period.")
                else:
                    suggestions.append("Shift one class to an alternate open period in the academic weekly timetable.")

                conflicts.append({
                    "id": f"cnf_room_{r_id}_{slot_id}",
                    "type": "ROOM_DOUBLE_BOOKING",
                    "severity": "CRITICAL",
                    "title": f"Room Double-Booking: {room_name}",
                    "description": f"Facility {room_name} has {len(conflicting_sessions)} simultaneous class bookings on {day_name} Period {p_num} ({time_range}).",
                    "day_number": slot.day_of_week if slot else 1,
                    "day_name": day_name,
                    "period_number": p_num,
                    "time_slot_id": slot_id,
                    "affected_classes": [session_summary(s) for s in conflicting_sessions],
                    "affected_resource_type": "ROOM",
                    "affected_resource_name": room_name,
                    "feasible_resolutions": suggestions,
                })

        # 3. Student Cohort Double-Booking Check
        for (c_id, slot_id), conflicting_sessions in cohort_slot_map.items():
            if len(conflicting_sessions) > 1:
                c_name = conflicting_sessions[0].cohort_section.section_name if conflicting_sessions[0].cohort_section else c_id
                slot = all_slots.get(slot_id)
                day_name = days_map.get(slot.day_of_week if slot else 1, "Unknown Day")
                p_num = slot.period_number if slot else 0

                conflicts.append({
                    "id": f"cnf_cohort_{c_id}_{slot_id}",
                    "type": "COHORT_DOUBLE_BOOKING",
                    "severity": "CRITICAL",
                    "title": f"Student Section Clash: {c_name}",
                    "description": f"Section {c_name} students are assigned to {len(conflicting_sessions)} different subjects at the same time on {day_name} Period {p_num}.",
                    "day_number": slot.day_of_week if slot else 1,
                    "day_name": day_name,
                    "period_number": p_num,
                    "time_slot_id": slot_id,
                    "affected_classes": [session_summary(s) for s in conflicting_sessions],
                    "affected_resource_type": "COHORT",
                    "affected_resource_name": c_name,
                    "feasible_resolutions": ["Reassign the conflicting subject to an unallocated time slot for this cohort section."],
                })

        # 4. Individual Session Checks (Capacity, Room Type, Break, Availability)
        for s in sessions:
            r = all_rooms.get(s.room_id)
            c = s.cohort_section
            slot = all_slots.get(s.time_slot_id)
            day_name = days_map.get(slot.day_of_week if slot else 1, "Unknown Day")
            p_num = slot.period_number if slot else 0

            # Room Capacity Violation
            if r and c and r.capacity < c.student_count:
                conflicts.append({
                    "id": f"cnf_cap_{s.id}",
                    "type": "ROOM_CAPACITY_VIOLATION",
                    "severity": "CRITICAL",
                    "title": f"Room Capacity Violation: {r.building} {r.room_number}",
                    "description": f"Classroom {r.building} {r.room_number} (Capacity: {r.capacity}) cannot accommodate Section {c.section_name} ({c.student_count} enrolled students) for '{s.subject.name if s.subject else ''}'.",
                    "day_number": slot.day_of_week if slot else 1,
                    "day_name": day_name,
                    "period_number": p_num,
                    "time_slot_id": s.time_slot_id,
                    "affected_classes": [session_summary(s)],
                    "affected_resource_type": "ROOM",
                    "affected_resource_name": f"{r.building} {r.room_number}",
                    "feasible_resolutions": [f"Reassign to an available larger facility with capacity >= {c.student_count}."],
                })

            # Room Type / Lab Suitability Violation
            if r and s.subject and hasattr(s.subject, "required_room_type") and s.subject.required_room_type:
                req_room_val = s.subject.required_room_type.value if hasattr(s.subject.required_room_type, "value") else str(s.subject.required_room_type)
                room_val = r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type)
                if req_room_val != room_val:
                    conflicts.append({
                        "id": f"cnf_type_{s.id}",
                        "type": "ROOM_SUITABILITY_VIOLATION",
                        "severity": "CRITICAL",
                        "title": f"Facility Requirement Mismatch: {s.subject.code}",
                        "description": f"Subject '{s.subject.name}' mandates '{req_room_val}', but is assigned to '{room_val}' ({r.building} {r.room_number}).",
                        "day_number": slot.day_of_week if slot else 1,
                        "day_name": day_name,
                        "period_number": p_num,
                        "time_slot_id": s.time_slot_id,
                        "affected_classes": [session_summary(s)],
                        "affected_resource_type": "ROOM",
                        "affected_resource_name": f"{r.building} {r.room_number}",
                        "feasible_resolutions": [f"Reassign to a verified {req_room_val} facility."],
                    })

            # Operating Hours / Break Period Violation
            if slot and slot.is_break:
                conflicts.append({
                    "id": f"cnf_break_{s.id}",
                    "type": "OPERATING_HOURS_VIOLATION",
                    "severity": "CRITICAL",
                    "title": f"Session Scheduled in Break Period: {day_name} P{p_num}",
                    "description": f"Session for '{s.subject.name if s.subject else ''}' is scheduled during an institutional recess/lunch period.",
                    "day_number": slot.day_of_week,
                    "day_name": day_name,
                    "period_number": p_num,
                    "time_slot_id": s.time_slot_id,
                    "affected_classes": [session_summary(s)],
                    "affected_resource_type": "TIMESLOT",
                    "affected_resource_name": f"Break Period {p_num}",
                    "feasible_resolutions": ["Shift session to standard academic teaching periods (1 through 6)."],
                })

            # Teacher Availability Violation
            if s.time_slot_id in unavail_slots_by_teacher.get(s.teacher_id, set()):
                t_name = s.teacher.full_name if s.teacher else s.teacher_id
                conflicts.append({
                    "id": f"cnf_avail_{s.id}",
                    "type": "TEACHER_AVAILABILITY_VIOLATION",
                    "severity": "CRITICAL",
                    "title": f"Faculty Unavailability: {t_name}",
                    "description": f"Faculty {t_name} is marked as unavailable/on leave during {day_name} Period {p_num}.",
                    "day_number": slot.day_of_week if slot else 1,
                    "day_name": day_name,
                    "period_number": p_num,
                    "time_slot_id": s.time_slot_id,
                    "affected_classes": [session_summary(s)],
                    "affected_resource_type": "TEACHER",
                    "affected_resource_name": t_name,
                    "feasible_resolutions": [
                        "Swap session to a slot matching faculty availability.",
                        "Assign an alternative faculty member.",
                    ],
                })

        critical_count = sum(1 for c in conflicts if c["severity"] == "CRITICAL")
        warning_count = sum(1 for c in conflicts if c["severity"] == "WARNING")
        is_conflict_free = critical_count == 0

        return {
            "timetable_id": timetable_id,
            "version_str": f"v{timetable.version_major}.{timetable.version_minor}",
            "status": timetable.status.value,
            "total_sessions": len(sessions),
            "is_conflict_free": is_conflict_free,
            "critical_conflicts_count": critical_count,
            "warnings_count": warning_count,
            "conflicts": conflicts,
            "checked_constraints": [
                "Teacher Double-Booking",
                "Room & Lab Double-Booking",
                "Student Section Overlaps",
                "Room Capacity Compliance",
                "Lab & Facility Suitability",
                "Institutional Break & Operating Hours",
                "Teacher Availability Constraints",
            ],
        }
