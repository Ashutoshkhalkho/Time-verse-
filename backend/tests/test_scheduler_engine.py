import pytest

from app.services.scheduler.engine import TimetableSolver
from app.services.scheduler.schemas import (
    CohortSectionInput,
    LockedSessionInput,
    RoomScheduleInput,
    SchedulingConfig,
    SolverStatusEnum,
    SubjectRequirementInput,
    TeacherScheduleInput,
    TimeSlotInput,
)


@pytest.fixture
def base_scheduling_inputs():
    """Provides a small, consistent test scheduling problem."""
    # 5 days x 5 periods (25 usable slots)
    slots = []
    for d in range(1, 6):
        for p in range(1, 6):
            slots.append(
                TimeSlotInput(
                    id=f"ts_d{d}_p{p}",
                    day_of_week=d,
                    period_number=p,
                    is_break=False,
                )
            )

    rooms = [
        RoomScheduleInput(id="rm_lh1", building="A", room_number="101", capacity=50, room_type="LECTURE_HALL"),
        RoomScheduleInput(id="rm_lh2", building="A", room_number="102", capacity=50, room_type="LECTURE_HALL"),
        RoomScheduleInput(id="rm_lab1", building="B", room_number="LAB1", capacity=40, room_type="COMPUTER_LAB"),
    ]

    teachers = [
        TeacherScheduleInput(id="tch_01", name="Dr. Sharma", max_hours_per_day=5, max_weekly_hours=20),
        TeacherScheduleInput(id="tch_02", name="Prof. Gupta", max_hours_per_day=5, max_weekly_hours=20),
    ]

    cohorts = [
        CohortSectionInput(id="sec_01", department_id="dept_cs", section_name="CS-A", student_count=35),
    ]

    requirements = [
        SubjectRequirementInput(
            id="req_01",
            cohort_section_id="sec_01",
            subject_id="sub_ds",
            subject_code="CS101",
            subject_name="Data Structures",
            subject_type="THEORY",
            teacher_id="tch_01",
            required_room_type="LECTURE_HALL",
            required_sessions_per_week=4,
        ),
        SubjectRequirementInput(
            id="req_02",
            cohort_section_id="sec_01",
            subject_id="sub_dslab",
            subject_code="CS101L",
            subject_name="DS Lab",
            subject_type="LABORATORY",
            teacher_id="tch_01",
            required_room_type="COMPUTER_LAB",
            required_sessions_per_week=2,
        ),
        SubjectRequirementInput(
            id="req_03",
            cohort_section_id="sec_01",
            subject_id="sub_dbms",
            subject_code="CS102",
            subject_name="Database Systems",
            subject_type="THEORY",
            teacher_id="tch_02",
            required_room_type="LECTURE_HALL",
            required_sessions_per_week=4,
        ),
    ]

    return {
        "slots": slots,
        "rooms": rooms,
        "teachers": teachers,
        "cohorts": cohorts,
        "requirements": requirements,
    }


def test_solver_feasible_schedule(base_scheduling_inputs):
    """Verifies that OR-Tools CP-SAT generates an optimal/feasible schedule fulfilling all requirements."""
    data = base_scheduling_inputs
    solver = TimetableSolver(
        teachers=data["teachers"],
        rooms=data["rooms"],
        time_slots=data["slots"],
        cohorts=data["cohorts"],
        requirements=data["requirements"],
        config=SchedulingConfig(time_limit_seconds=10.0),
    )
    result = solver.solve()

    assert result.status in {SolverStatusEnum.OPTIMAL, SolverStatusEnum.FEASIBLE}
    assert result.wall_time_seconds > 0.0
    # Expected total sessions: 4 + 2 + 4 = 10
    assert len(result.sessions) == 10
    assert len(result.diagnostics) == 0


def test_solver_detects_infeasible_teacher_hours(base_scheduling_inputs):
    """Verifies that solver identifies when teacher availability cannot fulfill requested demand."""
    data = base_scheduling_inputs

    # Dr. Sharma demands 4 + 2 = 6 periods, but mark 22 out of 25 slots as unavailable (leaving only 3 slots)
    all_slot_ids = [s.id for s in data["slots"]]
    unavail_22_slots = frozenset(all_slot_ids[:23])  # leaves only 2 slots available

    data["teachers"][0] = TeacherScheduleInput(
        id="tch_01",
        name="Dr. Sharma",
        max_hours_per_day=5,
        max_weekly_hours=20,
        unavailable_slot_ids=unavail_22_slots,
    )

    solver = TimetableSolver(
        teachers=data["teachers"],
        rooms=data["rooms"],
        time_slots=data["slots"],
        cohorts=data["cohorts"],
        requirements=data["requirements"],
    )
    result = solver.solve()

    assert result.status == SolverStatusEnum.INFEASIBLE
    assert len(result.sessions) == 0
    assert len(result.diagnostics) > 0
    assert "Dr. Sharma" in result.diagnostics[0]


def test_solver_detects_infeasible_room_capacity(base_scheduling_inputs):
    """Verifies that solver rejects schedule when student count exceeds all room capacities."""
    data = base_scheduling_inputs
    # Cohort has 80 students, but rooms only hold 50
    data["cohorts"][0] = CohortSectionInput(
        id="sec_01",
        department_id="dept_cs",
        section_name="CS-A",
        student_count=80,
    )

    solver = TimetableSolver(
        teachers=data["teachers"],
        rooms=data["rooms"],
        time_slots=data["slots"],
        cohorts=data["cohorts"],
        requirements=data["requirements"],
    )
    result = solver.solve()

    assert result.status == SolverStatusEnum.INFEASIBLE
    assert len(result.sessions) == 0
    assert any("capacity" in d.lower() for d in result.diagnostics)


def test_solver_detects_missing_suitable_lab(base_scheduling_inputs):
    """Verifies that solver identifies when a subject requires a room type not available in infrastructure."""
    data = base_scheduling_inputs
    # Remove the computer lab
    data["rooms"] = [r for r in data["rooms"] if r.room_type != "COMPUTER_LAB"]

    solver = TimetableSolver(
        teachers=data["teachers"],
        rooms=data["rooms"],
        time_slots=data["slots"],
        cohorts=data["cohorts"],
        requirements=data["requirements"],
    )
    result = solver.solve()

    assert result.status == SolverStatusEnum.INFEASIBLE
    assert len(result.sessions) == 0
    assert any("COMPUTER_LAB" in d for d in result.diagnostics)


def test_solver_enforces_locked_sessions(base_scheduling_inputs):
    """Verifies that solver strictly locks a specified session into the target slot and room."""
    data = base_scheduling_inputs
    # Lock DS Lab (req_02) on Day 1 Period 2 in rm_lab1
    locked = [
        LockedSessionInput(
            requirement_id="req_02",
            cohort_section_id="sec_01",
            subject_id="sub_dslab",
            teacher_id="tch_01",
            room_id="rm_lab1",
            time_slot_id="ts_d1_p2",
        )
    ]

    solver = TimetableSolver(
        teachers=data["teachers"],
        rooms=data["rooms"],
        time_slots=data["slots"],
        cohorts=data["cohorts"],
        requirements=data["requirements"],
        locked_sessions=locked,
        config=SchedulingConfig(time_limit_seconds=10.0),
    )
    result = solver.solve()

    assert result.status in {SolverStatusEnum.OPTIMAL, SolverStatusEnum.FEASIBLE}
    # Check that req_02 is scheduled at Day 1 Period 2 in rm_lab1
    locked_match = [
        s for s in result.sessions
        if s.requirement_id == "req_02" and s.time_slot_id == "ts_d1_p2" and s.room_id == "rm_lab1"
    ]
    assert len(locked_match) == 1
    assert locked_match[0].is_locked is True


def test_solver_detects_infeasible_locked_session(base_scheduling_inputs):
    """Verifies that solver detects conflict if a locked session places teacher in unavailable slot."""
    data = base_scheduling_inputs
    # Mark tch_01 unavailable on ts_d1_p1
    data["teachers"][0] = TeacherScheduleInput(
        id="tch_01",
        name="Dr. Sharma",
        max_hours_per_day=5,
        max_weekly_hours=20,
        unavailable_slot_ids=frozenset(["ts_d1_p1"]),
    )
    # Attempt to lock req_01 (taught by tch_01) in ts_d1_p1
    locked = [
        LockedSessionInput(
            requirement_id="req_01",
            cohort_section_id="sec_01",
            subject_id="sub_ds",
            teacher_id="tch_01",
            room_id="rm_lh1",
            time_slot_id="ts_d1_p1",
        )
    ]

    solver = TimetableSolver(
        teachers=data["teachers"],
        rooms=data["rooms"],
        time_slots=data["slots"],
        cohorts=data["cohorts"],
        requirements=data["requirements"],
        locked_sessions=locked,
    )
    result = solver.solve()

    assert result.status == SolverStatusEnum.INFEASIBLE
    assert len(result.sessions) == 0
    assert any("locked session" in d.lower() for d in result.diagnostics)

