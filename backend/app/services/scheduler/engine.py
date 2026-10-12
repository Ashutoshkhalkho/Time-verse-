import time
from collections import defaultdict

from ortools.sat.python import cp_model

from app.services.scheduler.schemas import (
    CohortSectionInput,
    LockedSessionInput,
    RoomScheduleInput,
    ScheduledSession,
    SchedulingConfig,
    SolverResult,
    SolverStatusEnum,
    SubjectRequirementInput,
    TeacherScheduleInput,
    TimeSlotInput,
)


class TimetableSolver:
    """
    Intelligent Timetable Planning & Generation Engine using Google OR-Tools CP-SAT.
    Strictly separates hard feasibility constraints from configurable soft preferences.
    """

    def __init__(
        self,
        teachers: list[TeacherScheduleInput],
        rooms: list[RoomScheduleInput],
        time_slots: list[TimeSlotInput],
        cohorts: list[CohortSectionInput],
        requirements: list[SubjectRequirementInput],
        locked_sessions: list[LockedSessionInput] | None = None,
        config: SchedulingConfig | None = None,
    ):
        self.teachers = {t.id: t for t in teachers}
        self.rooms = {r.id: r for r in rooms}
        self.time_slots = {ts.id: ts for ts in time_slots}
        self.cohorts = {c.id: c for c in cohorts}
        self.requirements = {req.id: req for req in requirements}
        self.locked_sessions = locked_sessions or []
        self.config = config or SchedulingConfig()

        # Usable slots (excluding breaks)
        self.usable_slots = [ts for ts in time_slots if not ts.is_break]

    def solve(self) -> SolverResult:
        start_time = time.perf_counter()

        # Step 0: Pre-flight Feasibility Diagnostics
        preflight_diagnostics = self._run_preflight_checks()
        if preflight_diagnostics:
            elapsed = time.perf_counter() - start_time
            return SolverResult(
                status=SolverStatusEnum.INFEASIBLE,
                wall_time_seconds=elapsed,
                objective_value=None,
                sessions=[],
                diagnostics=preflight_diagnostics,
                metrics={"preflight_failed": True},
            )

        model = cp_model.CpModel()

        # Decision variables: X[req_id, room_id, slot_id] -> 0 or 1
        x: dict[tuple[str, str, str], cp_model.IntVar] = {}

        # Pre-filter candidate rooms for each requirement based on hard constraints
        # Hard constraint: Room capacity >= student_count AND Room type matches required_room_type
        candidate_rooms_by_req: dict[str, list[RoomScheduleInput]] = {}
        for req_id, req in self.requirements.items():
            cohort = self.cohorts.get(req.cohort_section_id)
            min_capacity = cohort.student_count if cohort else 0

            matching_rooms = [
                r
                for r in self.rooms.values()
                if r.is_active
                and r.room_type == req.required_room_type
                and r.capacity >= min_capacity
            ]
            candidate_rooms_by_req[req_id] = matching_rooms

            if not matching_rooms:
                elapsed = time.perf_counter() - start_time
                diag = (
                    f"Infeasible Requirement '{req.subject_code}' for Section '{cohort.section_name if cohort else req.cohort_section_id}': "
                    f"No active room exists with type '{req.required_room_type}' and capacity >= {min_capacity}."
                )
                return SolverResult(
                    status=SolverStatusEnum.INFEASIBLE,
                    wall_time_seconds=elapsed,
                    objective_value=None,
                    sessions=[],
                    diagnostics=[diag],
                    metrics={"missing_rooms": True},
                )

        # Ensure candidate rooms include room specified by locked sessions
        for lk in self.locked_sessions:
            target_req_id = lk.requirement_id
            if not target_req_id and lk.cohort_section_id and lk.subject_id:
                for r_id, r in self.requirements.items():
                    if r.cohort_section_id == lk.cohort_section_id and r.subject_id == lk.subject_id:
                        target_req_id = r_id
                        break
            if target_req_id and target_req_id in candidate_rooms_by_req:
                lk_room = self.rooms.get(lk.room_id)
                if lk_room and lk_room not in candidate_rooms_by_req[target_req_id]:
                    candidate_rooms_by_req[target_req_id].append(lk_room)

        # Create decision variables for all feasible (req, room, slot) triplets
        for req_id, req in self.requirements.items():
            teacher = self.teachers.get(req.teacher_id)
            unavail_slots = teacher.unavailable_slot_ids if teacher else frozenset()

            for room in candidate_rooms_by_req[req_id]:
                for slot in self.usable_slots:
                    # Hard Constraint: Teacher cannot be assigned if marked unavailable
                    if slot.id in unavail_slots:
                        continue

                    var_name = f"x_{req_id}_{room.id}_{slot.id}"
                    x[req_id, room.id, slot.id] = model.NewBoolVar(var_name)

        # Hard Constraint 0: Enforce Locked Sessions
        for lk in self.locked_sessions:
            target_req_id = lk.requirement_id
            if not target_req_id and lk.cohort_section_id and lk.subject_id:
                for r_id, r in self.requirements.items():
                    if r.cohort_section_id == lk.cohort_section_id and r.subject_id == lk.subject_id:
                        target_req_id = r_id
                        break
            if target_req_id and target_req_id in self.requirements:
                if (target_req_id, lk.room_id, lk.time_slot_id) not in x:
                    x[target_req_id, lk.room_id, lk.time_slot_id] = model.NewBoolVar(
                        f"x_lk_{target_req_id}_{lk.room_id}_{lk.time_slot_id}"
                    )
                model.Add(x[target_req_id, lk.room_id, lk.time_slot_id] == 1)

        # -------------------------------------------------------------
        # HARD CONSTRAINTS
        # -------------------------------------------------------------

        # Hard Constraint 1: Session Fulfillment
        # Each requirement must have exactly required_sessions_per_week slots assigned
        for req_id, req in self.requirements.items():
            assigned_vars = [
                x[req_id, r.id, s.id]
                for r in candidate_rooms_by_req[req_id]
                for s in self.usable_slots
                if (req_id, r.id, s.id) in x
            ]
            if not assigned_vars:
                elapsed = time.perf_counter() - start_time
                diag = (
                    f"Teacher '{self.teachers.get(req.teacher_id, req.teacher_id)}' is unavailable "
                    f"for all possible slots required to fulfill '{req.subject_code}'."
                )
                return SolverResult(
                    status=SolverStatusEnum.INFEASIBLE,
                    wall_time_seconds=elapsed,
                    objective_value=None,
                    sessions=[],
                    diagnostics=[diag],
                )
            model.Add(sum(assigned_vars) == req.required_sessions_per_week)

        # Hard Constraint 2: No Teacher Double-Booking
        # At any slot, a teacher can teach at most 1 session
        for teacher_id in self.teachers:
            teacher_reqs = [
                req_id for req_id, req in self.requirements.items() if req.teacher_id == teacher_id
            ]
            for slot in self.usable_slots:
                slot_teacher_vars = [
                    x[req_id, room_id, slot.id]
                    for req_id in teacher_reqs
                    for room_id in [r.id for r in candidate_rooms_by_req[req_id]]
                    if (req_id, room_id, slot.id) in x
                ]
                if slot_teacher_vars:
                    model.Add(sum(slot_teacher_vars) <= 1)

        # Hard Constraint 3: No Room Double-Booking
        # At any slot, a room can host at most 1 session
        for room_id in self.rooms:
            for slot in self.usable_slots:
                slot_room_vars = [
                    x[req_id, room_id, slot.id]
                    for req_id in self.requirements
                    if (req_id, room_id, slot.id) in x
                ]
                if slot_room_vars:
                    model.Add(sum(slot_room_vars) <= 1)

        # Hard Constraint 4: No Student Cohort Double-Booking
        # At any slot, a cohort section can attend at most 1 session
        for cohort_id in self.cohorts:
            cohort_reqs = [
                req_id
                for req_id, req in self.requirements.items()
                if req.cohort_section_id == cohort_id
            ]
            for slot in self.usable_slots:
                slot_cohort_vars = [
                    x[req_id, room_id, slot.id]
                    for req_id in cohort_reqs
                    for room_id in [r.id for r in candidate_rooms_by_req[req_id]]
                    if (req_id, room_id, slot.id) in x
                ]
                if slot_cohort_vars:
                    model.Add(sum(slot_cohort_vars) <= 1)

        # Hard Constraint 5: Teacher Max Hours Per Day
        # Group usable slots by day
        slots_by_day = defaultdict(list)
        for s in self.usable_slots:
            slots_by_day[s.day_of_week].append(s)

        for teacher_id, teacher in self.teachers.items():
            teacher_reqs = [
                req_id for req_id, req in self.requirements.items() if req.teacher_id == teacher_id
            ]
            for _day, day_slots in slots_by_day.items():
                day_teacher_vars = [
                    x[req_id, room_id, s.id]
                    for req_id in teacher_reqs
                    for room_id in [r.id for r in candidate_rooms_by_req[req_id]]
                    for s in day_slots
                    if (req_id, room_id, s.id) in x
                ]
                if day_teacher_vars:
                    model.Add(sum(day_teacher_vars) <= teacher.max_hours_per_day)

        # Hard Constraint 6: Cohort Max Sessions Per Day
        for cohort_id in self.cohorts:
            cohort_reqs = [
                req_id
                for req_id, req in self.requirements.items()
                if req.cohort_section_id == cohort_id
            ]
            for _day, day_slots in slots_by_day.items():
                day_cohort_vars = [
                    x[req_id, room_id, s.id]
                    for req_id in cohort_reqs
                    for room_id in [r.id for r in candidate_rooms_by_req[req_id]]
                    for s in day_slots
                    if (req_id, room_id, s.id) in x
                ]
                if day_cohort_vars:
                    model.Add(sum(day_cohort_vars) <= self.config.max_daily_sessions_per_cohort)

        # -------------------------------------------------------------
        # SOFT PREFERENCES & OBJECTIVE FUNCTION
        # -------------------------------------------------------------
        objective_terms = []

        # Soft Preference 1: Preferred Teaching Times
        # Teacher preference weights: -2 (avoid), +2 (preferred)
        for (req_id, _room_id, slot_id), var in x.items():
            req = self.requirements[req_id]
            teacher = self.teachers.get(req.teacher_id)
            if teacher and slot_id in teacher.preference_weights:
                pref_score = teacher.preference_weights[slot_id]
                weight = self.config.weight_preferred_times * pref_score
                objective_terms.append(weight * var)

        # Soft Preference 2: Preferred Room Assignment
        for (req_id, room_id, _slot_id), var in x.items():
            req = self.requirements[req_id]
            if req.preferred_room_id and room_id == req.preferred_room_id:
                objective_terms.append(10 * var)

        # Soft Preference 3: Balanced Workload
        # Encourage spreading sessions across available days (max 2 sessions per subject per day)
        for req_id, _req in self.requirements.items():
            for day, day_slots in slots_by_day.items():
                day_subject_vars = [
                    x[req_id, r.id, s.id]
                    for r in candidate_rooms_by_req[req_id]
                    for s in day_slots
                    if (req_id, r.id, s.id) in x
                ]
                if day_subject_vars and len(day_subject_vars) > 2:
                    # Soft penalty for scheduling > 2 sessions of same subject on same day
                    excess_var = model.NewIntVar(0, len(day_subject_vars), f"excess_{req_id}_{day}")
                    model.Add(sum(day_subject_vars) - 2 <= excess_var)
                    objective_terms.append(-self.config.weight_balanced_daily_workload * excess_var)

        if objective_terms:
            model.Maximize(sum(objective_terms))

        # -------------------------------------------------------------
        # SOLVER EXECUTION
        # -------------------------------------------------------------
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.time_limit_seconds
        solver.parameters.num_search_workers = 4

        status_code = solver.Solve(model)
        elapsed = time.perf_counter() - start_time

        if status_code == cp_model.OPTIMAL:
            status = SolverStatusEnum.OPTIMAL
        elif status_code == cp_model.FEASIBLE:
            status = SolverStatusEnum.FEASIBLE
        elif status_code == cp_model.INFEASIBLE:
            status = SolverStatusEnum.INFEASIBLE
        elif status_code == cp_model.MODEL_INVALID:
            status = SolverStatusEnum.MODEL_INVALID
        else:
            status = SolverStatusEnum.TIME_LIMIT

        if status in {SolverStatusEnum.OPTIMAL, SolverStatusEnum.FEASIBLE}:
            scheduled_sessions: list[ScheduledSession] = []
            for (req_id, room_id, slot_id), var in x.items():
                if solver.Value(var) == 1:
                    req = self.requirements[req_id]
                    slot = self.time_slots[slot_id]
                    is_locked = any(
                        (
                            (lk.requirement_id == req_id)
                            or (
                                lk.cohort_section_id == req.cohort_section_id
                                and lk.subject_id == req.subject_id
                            )
                        )
                        and lk.room_id == room_id
                        and lk.time_slot_id == slot_id
                        for lk in self.locked_sessions
                    )
                    scheduled_sessions.append(
                        ScheduledSession(
                            requirement_id=req_id,
                            cohort_section_id=req.cohort_section_id,
                            subject_id=req.subject_id,
                            teacher_id=req.teacher_id,
                            room_id=room_id,
                            time_slot_id=slot_id,
                            day_of_week=slot.day_of_week,
                            period_number=slot.period_number,
                            is_locked=is_locked,
                        )
                    )

            return SolverResult(
                status=status,
                wall_time_seconds=elapsed,
                objective_value=solver.ObjectiveValue() if objective_terms else 0.0,
                sessions=scheduled_sessions,
                diagnostics=[],
                metrics={
                    "total_sessions": len(scheduled_sessions),
                    "branches": solver.NumBranches(),
                    "conflicts": solver.NumConflicts(),
                },
            )
        else:
            diagnostics = self._generate_infeasible_diagnostics()
            return SolverResult(
                status=status,
                wall_time_seconds=elapsed,
                objective_value=None,
                sessions=[],
                diagnostics=diagnostics,
                metrics={
                    "conflicts": solver.NumConflicts(),
                    "branches": solver.NumBranches(),
                },
            )

    def _run_preflight_checks(self) -> list[str]:
        """Performs fast analytical bounds checks before invoking CP-SAT."""
        diagnostics = []

        total_slots_available = len(self.usable_slots)
        if total_slots_available == 0:
            return ["No usable non-break time slots configured in the institution schedule."]

        # Check total cohort demand vs total slots
        for cohort_id, cohort in self.cohorts.items():
            demand = sum(
                req.required_sessions_per_week
                for req in self.requirements.values()
                if req.cohort_section_id == cohort_id
            )
            if demand > total_slots_available:
                diagnostics.append(
                    f"Cohort '{cohort.section_name}' demands {demand} weekly periods, but only {total_slots_available} usable slots exist."
                )

        # Check teacher availability bounds
        for teacher_id, teacher in self.teachers.items():
            demand = sum(
                req.required_sessions_per_week
                for req in self.requirements.values()
                if req.teacher_id == teacher_id
            )
            available_slots = total_slots_available - len(teacher.unavailable_slot_ids)
            if demand > available_slots:
                diagnostics.append(
                    f"Teacher '{teacher.name}' (ID: {teacher_id}) is demanded for {demand} periods, "
                    f"but only available for {available_slots} periods ({len(teacher.unavailable_slot_ids)} slots marked unavailable)."
                )
            if demand > teacher.max_weekly_hours:
                diagnostics.append(
                    f"Teacher '{teacher.name}' is demanded for {demand} periods, exceeding weekly cap of {teacher.max_weekly_hours} hours."
                )

        # Check locked sessions preflight feasibility
        for lk in self.locked_sessions:
            if lk.time_slot_id not in self.time_slots:
                diagnostics.append(f"Locked session refers to invalid slot ID '{lk.time_slot_id}'.")
                continue
            slot = self.time_slots[lk.time_slot_id]
            if slot.is_break:
                diagnostics.append(f"Locked session assigned to break slot (Day {slot.day_of_week} Period {slot.period_number}).")
            if lk.room_id not in self.rooms:
                diagnostics.append(f"Locked session refers to invalid room ID '{lk.room_id}'.")
                continue
            room = self.rooms[lk.room_id]
            if not room.is_active:
                diagnostics.append(f"Locked session is assigned to inactive room '{room.building}-{room.room_number}'.")

            target_req = self.requirements.get(lk.requirement_id) if lk.requirement_id else None
            if not target_req and lk.cohort_section_id and lk.subject_id:
                for r in self.requirements.values():
                    if r.cohort_section_id == lk.cohort_section_id and r.subject_id == lk.subject_id:
                        target_req = r
                        break
            if target_req:
                cohort = self.cohorts.get(target_req.cohort_section_id)
                if cohort and room.capacity < cohort.student_count:
                    diagnostics.append(
                        f"Locked session capacity conflict: Room '{room.building}-{room.room_number}' (Capacity: {room.capacity}) "
                        f"cannot fit Section '{cohort.section_name}' ({cohort.student_count} students) for locked '{target_req.subject_code}'."
                    )
                if room.room_type != target_req.required_room_type:
                    diagnostics.append(
                        f"Locked session room type conflict: Subject '{target_req.subject_code}' requires '{target_req.required_room_type}', "
                        f"but locked room '{room.building}-{room.room_number}' is '{room.room_type}'."
                    )
                teacher = self.teachers.get(target_req.teacher_id)
                if teacher and lk.time_slot_id in teacher.unavailable_slot_ids:
                    diagnostics.append(
                        f"Locked session faculty conflict: Teacher '{teacher.name}' is marked unavailable at "
                        f"Day {slot.day_of_week} Period {slot.period_number} for locked '{target_req.subject_code}'."
                    )

        return diagnostics

    def _generate_infeasible_diagnostics(self) -> list[str]:
        """Provides human-readable diagnostic explanations when the solver returns INFEASIBLE."""
        reasons = [
            "Solver determined the problem is mathematically INFEASIBLE.",
            "Potential bottleneck: High overlap of shared faculty or limited specialized lab rooms.",
            "Recommendation: Check faculty unavailable slots, increase room availability, or adjust section periods.",
        ]
        return reasons
