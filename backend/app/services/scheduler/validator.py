from collections import defaultdict

from app.services.scheduler.schemas import (
    CohortSectionInput,
    LockedSessionInput,
    RoomScheduleInput,
    ScheduledSession,
    SubjectRequirementInput,
    TeacherScheduleInput,
    TimeSlotInput,
    ValidationResult,
)


class TimetableValidator:
    """
    Independent validation engine verifying generated and proposed timetables.
    Evaluates every hard constraint and returns human-readable conflict diagnostics.
    Never marks an invalid or unverified schedule as valid.
    """

    def __init__(
        self,
        teachers: dict[str, TeacherScheduleInput],
        rooms: dict[str, RoomScheduleInput],
        time_slots: dict[str, TimeSlotInput],
        cohorts: dict[str, CohortSectionInput],
        requirements: dict[str, SubjectRequirementInput],
    ):
        self.teachers = {t.id: t for t in teachers} if isinstance(teachers, list) else teachers
        self.rooms = {r.id: r for r in rooms} if isinstance(rooms, list) else rooms
        self.time_slots = {ts.id: ts for ts in time_slots} if isinstance(time_slots, list) else time_slots
        self.cohorts = {c.id: c for c in cohorts} if isinstance(cohorts, list) else cohorts
        self.requirements = {req.id: req for req in requirements} if isinstance(requirements, list) else requirements

    def validate(
        self,
        sessions: list[ScheduledSession],
        locked_sessions: list[LockedSessionInput] | None = None,
    ) -> ValidationResult:
        hard_violations: list[str] = []
        soft_warnings: list[str] = []

        # Maps for conflict detection
        teacher_slot_sessions = defaultdict(list)
        room_slot_sessions = defaultdict(list)
        cohort_slot_sessions = defaultdict(list)
        req_scheduled_count = defaultdict(int)

        # Track daily sessions per teacher and cohort
        teacher_day_count = defaultdict(lambda: defaultdict(int))
        cohort_day_count = defaultdict(lambda: defaultdict(int))

        for _idx, s in enumerate(sessions):
            slot = self.time_slots.get(s.time_slot_id)
            teacher = self.teachers.get(s.teacher_id)
            room = self.rooms.get(s.room_id)
            cohort = self.cohorts.get(s.cohort_section_id)
            req = self.requirements.get(s.requirement_id)

            slot_desc = (
                f"Day {slot.day_of_week} Period {slot.period_number}"
                if slot
                else f"Slot {s.time_slot_id}"
            )
            subj_name = req.subject_name if req else s.subject_id
            cohort_name = cohort.section_name if cohort else s.cohort_section_id
            teacher_name = teacher.name if teacher else s.teacher_id
            room_name = f"{room.building}-{room.room_number}" if room else s.room_id

            # Hard Constraint Check 1: Institutional Operating Hours & Breaks
            if slot and slot.is_break:
                hard_violations.append(
                    f"Operating Hours Violation: Session for '{subj_name}' scheduled during break period at {slot_desc}."
                )

            # Hard Constraint Check 2: Inactive Rooms
            if room and not room.is_active:
                hard_violations.append(
                    f"Inactive Room Violation: Room '{room_name}' is deactivated but assigned to '{subj_name}' at {slot_desc}."
                )

            # Hard Constraint Check 3: Room Capacity
            if room and cohort:
                if room.capacity < cohort.student_count:
                    hard_violations.append(
                        f"Room Capacity Violation: Room '{room_name}' (Capacity: {room.capacity}) "
                        f"cannot accommodate Section '{cohort_name}' (Students: {cohort.student_count}) for '{subj_name}' at {slot_desc}."
                    )

            # Hard Constraint Check 4: Lab & Room Suitability
            if room and req:
                if room.room_type != req.required_room_type:
                    hard_violations.append(
                        f"Room Suitability Violation: Subject '{subj_name}' requires '{req.required_room_type}', "
                        f"but assigned Room '{room_name}' is of type '{room.room_type}' at {slot_desc}."
                    )

            # Hard Constraint Check 5: Teacher Availability
            if teacher and slot:
                if slot.id in teacher.unavailable_slot_ids:
                    hard_violations.append(
                        f"Teacher Availability Violation: Teacher '{teacher_name}' is unavailable at {slot_desc}, "
                        f"but assigned to teach '{subj_name}'."
                    )

            # Group for double-booking checks
            teacher_slot_sessions[(s.teacher_id, s.time_slot_id)].append(
                (subj_name, cohort_name, room_name, slot_desc)
            )
            room_slot_sessions[(s.room_id, s.time_slot_id)].append(
                (subj_name, cohort_name, teacher_name, slot_desc)
            )
            cohort_slot_sessions[(s.cohort_section_id, s.time_slot_id)].append(
                (subj_name, teacher_name, room_name, slot_desc)
            )
            req_scheduled_count[s.requirement_id] += 1

            if slot:
                teacher_day_count[s.teacher_id][slot.day_of_week] += 1
                cohort_day_count[s.cohort_section_id][slot.day_of_week] += 1

        # Hard Constraint Check 6: Teacher Double-Booking
        for (teacher_id, _slot_id), conflicting_entries in teacher_slot_sessions.items():
            if len(conflicting_entries) > 1:
                t_name = self.teachers[teacher_id].name if teacher_id in self.teachers else teacher_id
                slot_info = conflicting_entries[0][3]
                details = "; ".join(
                    f"'{entry[0]}' (Section: {entry[1]}, Room: {entry[2]})"
                    for entry in conflicting_entries
                )
                hard_violations.append(
                    f"Teacher Double-Booking: Teacher '{t_name}' has {len(conflicting_entries)} overlapping sessions at {slot_info}: {details}."
                )

        # Hard Constraint Check 7: Room Double-Booking
        for (room_id, _slot_id), conflicting_entries in room_slot_sessions.items():
            if len(conflicting_entries) > 1:
                r_name = (
                    f"{self.rooms[room_id].building}-{self.rooms[room_id].room_number}"
                    if room_id in self.rooms
                    else room_id
                )
                slot_info = conflicting_entries[0][3]
                details = "; ".join(
                    f"'{entry[0]}' (Section: {entry[1]}, Teacher: {entry[2]})"
                    for entry in conflicting_entries
                )
                hard_violations.append(
                    f"Room Double-Booking: Room '{r_name}' is double-booked with {len(conflicting_entries)} sessions at {slot_info}: {details}."
                )

        # Hard Constraint Check 8: Cohort Section Double-Booking
        for (cohort_id, _slot_id), conflicting_entries in cohort_slot_sessions.items():
            if len(conflicting_entries) > 1:
                c_name = self.cohorts[cohort_id].section_name if cohort_id in self.cohorts else cohort_id
                slot_info = conflicting_entries[0][3]
                details = "; ".join(
                    f"'{entry[0]}' (Teacher: {entry[1]}, Room: {entry[2]})"
                    for entry in conflicting_entries
                )
                hard_violations.append(
                    f"Cohort Double-Booking: Section '{c_name}' has {len(conflicting_entries)} overlapping sessions at {slot_info}: {details}."
                )

        # Hard Constraint Check 9: Curriculum Requirement Fulfillment
        for req_id, req in self.requirements.items():
            scheduled = req_scheduled_count[req_id]
            if scheduled != req.required_sessions_per_week:
                c_name = self.cohorts[req.cohort_section_id].section_name if req.cohort_section_id in self.cohorts else req.cohort_section_id
                hard_violations.append(
                    f"Requirement Fulfillment Violation: Subject '{req.subject_name}' for Section '{c_name}' "
                    f"demands {req.required_sessions_per_week} periods/week, but {scheduled} were scheduled."
                )

        # Hard Constraint Check 10: Locked Session Enforcement
        if locked_sessions:
            for lk in locked_sessions:
                # Find matching session
                matched = any(
                    s.time_slot_id == lk.time_slot_id
                    and s.room_id == lk.room_id
                    and (
                        (lk.requirement_id and s.requirement_id == lk.requirement_id)
                        or (lk.subject_id and s.subject_id == lk.subject_id)
                        or (not lk.requirement_id and not lk.subject_id)
                    )
                    for s in sessions
                )
                if not matched:
                    slot = self.time_slots.get(lk.time_slot_id)
                    slot_desc = (
                        f"Day {slot.day_of_week} Period {slot.period_number}"
                        if slot
                        else lk.time_slot_id
                    )
                    room = self.rooms.get(lk.room_id)
                    room_desc = f"{room.building}-{room.room_number}" if room else lk.room_id
                    hard_violations.append(
                        f"Locked Session Violation: Pre-locked session at {slot_desc} in Room '{room_desc}' was not scheduled."
                    )

        # Soft Constraint Check: Daily Hours & Workload Balance
        for teacher_id, days in teacher_day_count.items():
            teacher = self.teachers.get(teacher_id)
            if teacher:
                for day, count in days.items():
                    if count > teacher.max_hours_per_day:
                        soft_warnings.append(
                            f"High Daily Workload: Teacher '{teacher.name}' scheduled for {count} sessions on Day {day} (max: {teacher.max_hours_per_day})."
                        )

        is_valid = len(hard_violations) == 0

        return ValidationResult(
            is_valid=is_valid,
            hard_violations=hard_violations,
            soft_warnings=soft_warnings,
            metrics={
                "total_sessions": len(sessions),
                "hard_violation_count": len(hard_violations),
                "soft_warning_count": len(soft_warnings),
            },
        )
