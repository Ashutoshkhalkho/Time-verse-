import pytest

from app.services.scheduler.schemas import (
    CohortSectionInput,
    RoomScheduleInput,
    ScheduledSession,
    SubjectRequirementInput,
    TeacherScheduleInput,
    TimeSlotInput,
)
from app.services.scheduler.validator import TimetableValidator


@pytest.fixture
def validator_context():
    slots = {
        "ts_1": TimeSlotInput(id="ts_1", day_of_week=1, period_number=1, is_break=False),
        "ts_2": TimeSlotInput(id="ts_2", day_of_week=1, period_number=2, is_break=False),
        "ts_break": TimeSlotInput(id="ts_break", day_of_week=1, period_number=4, is_break=True),
    }
    rooms = {
        "rm_lh1": RoomScheduleInput(id="rm_lh1", building="Main", room_number="101", capacity=50, room_type="LECTURE_HALL"),
        "rm_lh2": RoomScheduleInput(id="rm_lh2", building="Main", room_number="103", capacity=50, room_type="LECTURE_HALL"),
        "rm_lab1": RoomScheduleInput(id="rm_lab1", building="Science", room_number="L1", capacity=40, room_type="COMPUTER_LAB"),
        "rm_small": RoomScheduleInput(id="rm_small", building="Main", room_number="102", capacity=25, room_type="LECTURE_HALL"),
        "rm_inactive": RoomScheduleInput(id="rm_inactive", building="Main", room_number="999", capacity=50, room_type="LECTURE_HALL", is_active=False),
    }
    teachers = {
        "tch_1": TeacherScheduleInput(id="tch_1", name="Dr. Sharma", max_hours_per_day=5, max_weekly_hours=20, unavailable_slot_ids=frozenset(["ts_2"])),
        "tch_2": TeacherScheduleInput(id="tch_2", name="Prof. Gupta", max_hours_per_day=5, max_weekly_hours=20),
    }
    cohorts = {
        "sec_a": CohortSectionInput(id="sec_a", department_id="dept_cs", section_name="CS-A", student_count=45),
        "sec_b": CohortSectionInput(id="sec_b", department_id="dept_cs", section_name="CS-B", student_count=30),
    }
    requirements = {
        "req_ds": SubjectRequirementInput(
            id="req_ds", cohort_section_id="sec_a", subject_id="sub_ds", subject_code="CS101",
            subject_name="Data Structures", subject_type="THEORY", teacher_id="tch_1",
            required_room_type="LECTURE_HALL", required_sessions_per_week=1,
        ),
        "req_db": SubjectRequirementInput(
            id="req_db", cohort_section_id="sec_b", subject_id="sub_db", subject_code="CS102",
            subject_name="DBMS", subject_type="THEORY", teacher_id="tch_2",
            required_room_type="LECTURE_HALL", required_sessions_per_week=1,
        ),
        "req_lab": SubjectRequirementInput(
            id="req_lab", cohort_section_id="sec_b", subject_id="sub_lab", subject_code="CS102L",
            subject_name="DBMS Lab", subject_type="LABORATORY", teacher_id="tch_2",
            required_room_type="COMPUTER_LAB", required_sessions_per_week=1,
        ),
    }
    return {
        "slots": slots,
        "rooms": rooms,
        "teachers": teachers,
        "cohorts": cohorts,
        "requirements": requirements,
    }


def test_validator_positive_valid_schedule(validator_context):
    """Verifies that a valid schedule passes the independent validator with zero hard violations."""
    ctx = validator_context
    validator = TimetableValidator(
        teachers=ctx["teachers"],
        rooms=ctx["rooms"],
        time_slots=ctx["slots"],
        cohorts=ctx["cohorts"],
        requirements=ctx["requirements"],
    )

    valid_sessions = [
        ScheduledSession(
            requirement_id="req_ds", cohort_section_id="sec_a", subject_id="sub_ds",
            teacher_id="tch_1", room_id="rm_lh1", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
        ScheduledSession(
            requirement_id="req_db", cohort_section_id="sec_b", subject_id="sub_db",
            teacher_id="tch_2", room_id="rm_lh2", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
    ]

    # Adjust req_lab so requirements dict matches exactly scheduled
    reqs_subset = {"req_ds": ctx["requirements"]["req_ds"], "req_db": ctx["requirements"]["req_db"]}
    validator.requirements = reqs_subset

    res = validator.validate(valid_sessions)
    assert res.is_valid is True
    assert len(res.hard_violations) == 0


def test_validator_detects_teacher_double_booking(validator_context):
    """Verifies that the validator flags teacher double-booking at the same time slot."""
    ctx = validator_context
    validator = TimetableValidator(
        teachers=ctx["teachers"],
        rooms=ctx["rooms"],
        time_slots=ctx["slots"],
        cohorts=ctx["cohorts"],
        requirements={"req_ds": ctx["requirements"]["req_ds"]},
    )

    conflict_sessions = [
        ScheduledSession(
            requirement_id="req_ds", cohort_section_id="sec_a", subject_id="sub_ds",
            teacher_id="tch_1", room_id="rm_lh1", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
        ScheduledSession(
            requirement_id="req_ds", cohort_section_id="sec_b", subject_id="sub_ds",
            teacher_id="tch_1", room_id="rm_small", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
    ]

    res = validator.validate(conflict_sessions)
    assert res.is_valid is False
    assert any("Teacher Double-Booking" in v for v in res.hard_violations)


def test_validator_detects_room_double_booking(validator_context):
    """Verifies that the validator flags room double-booking at the same time slot."""
    ctx = validator_context
    validator = TimetableValidator(
        teachers=ctx["teachers"],
        rooms=ctx["rooms"],
        time_slots=ctx["slots"],
        cohorts=ctx["cohorts"],
        requirements={"req_ds": ctx["requirements"]["req_ds"], "req_db": ctx["requirements"]["req_db"]},
    )

    conflict_sessions = [
        ScheduledSession(
            requirement_id="req_ds", cohort_section_id="sec_a", subject_id="sub_ds",
            teacher_id="tch_1", room_id="rm_lh1", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
        ScheduledSession(
            requirement_id="req_db", cohort_section_id="sec_b", subject_id="sub_db",
            teacher_id="tch_2", room_id="rm_lh1", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
    ]

    res = validator.validate(conflict_sessions)
    assert res.is_valid is False
    assert any("Room Double-Booking" in v for v in res.hard_violations)


def test_validator_detects_cohort_double_booking(validator_context):
    """Verifies that the validator flags cohort double-booking at the same time slot."""
    ctx = validator_context
    validator = TimetableValidator(
        teachers=ctx["teachers"],
        rooms=ctx["rooms"],
        time_slots=ctx["slots"],
        cohorts=ctx["cohorts"],
        requirements={"req_ds": ctx["requirements"]["req_ds"], "req_db": ctx["requirements"]["req_db"]},
    )

    conflict_sessions = [
        ScheduledSession(
            requirement_id="req_ds", cohort_section_id="sec_a", subject_id="sub_ds",
            teacher_id="tch_1", room_id="rm_lh1", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
        ScheduledSession(
            requirement_id="req_db", cohort_section_id="sec_a", subject_id="sub_db",
            teacher_id="tch_2", room_id="rm_small", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
    ]

    res = validator.validate(conflict_sessions)
    assert res.is_valid is False
    assert any("Cohort Double-Booking" in v for v in res.hard_violations)


def test_validator_detects_room_capacity_violation(validator_context):
    """Verifies that assigning a section of 45 students to a room with capacity 25 triggers a violation."""
    ctx = validator_context
    validator = TimetableValidator(
        teachers=ctx["teachers"],
        rooms=ctx["rooms"],
        time_slots=ctx["slots"],
        cohorts=ctx["cohorts"],
        requirements={"req_ds": ctx["requirements"]["req_ds"]},
    )

    sessions = [
        ScheduledSession(
            requirement_id="req_ds", cohort_section_id="sec_a", subject_id="sub_ds",
            teacher_id="tch_1", room_id="rm_small", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
    ]

    res = validator.validate(sessions)
    assert res.is_valid is False
    assert any("Room Capacity Violation" in v for v in res.hard_violations)


def test_validator_detects_lab_suitability_violation(validator_context):
    """Verifies that scheduling a lab in a standard lecture hall triggers a room suitability violation."""
    ctx = validator_context
    validator = TimetableValidator(
        teachers=ctx["teachers"],
        rooms=ctx["rooms"],
        time_slots=ctx["slots"],
        cohorts=ctx["cohorts"],
        requirements={"req_lab": ctx["requirements"]["req_lab"]},
    )

    sessions = [
        ScheduledSession(
            requirement_id="req_lab", cohort_section_id="sec_b", subject_id="sub_lab",
            teacher_id="tch_2", room_id="rm_lh1", time_slot_id="ts_1", day_of_week=1, period_number=1,
        ),
    ]

    res = validator.validate(sessions)
    assert res.is_valid is False
    assert any("Room Suitability Violation" in v for v in res.hard_violations)


def test_validator_detects_teacher_unavailability_violation(validator_context):
    """Verifies that assigning a session to a teacher during an unavailable slot triggers a violation."""
    ctx = validator_context
    validator = TimetableValidator(
        teachers=ctx["teachers"],
        rooms=ctx["rooms"],
        time_slots=ctx["slots"],
        cohorts=ctx["cohorts"],
        requirements={"req_ds": ctx["requirements"]["req_ds"]},
    )

    # tch_1 has ts_2 in unavailable_slot_ids
    sessions = [
        ScheduledSession(
            requirement_id="req_ds", cohort_section_id="sec_a", subject_id="sub_ds",
            teacher_id="tch_1", room_id="rm_lh1", time_slot_id="ts_2", day_of_week=1, period_number=2,
        ),
    ]

    res = validator.validate(sessions)
    assert res.is_valid is False
    assert any("Teacher Availability Violation" in v for v in res.hard_violations)


def test_validator_detects_break_period_violation(validator_context):
    """Verifies that scheduling during institutional break periods triggers a violation."""
    ctx = validator_context
    validator = TimetableValidator(
        teachers=ctx["teachers"],
        rooms=ctx["rooms"],
        time_slots=ctx["slots"],
        cohorts=ctx["cohorts"],
        requirements={"req_ds": ctx["requirements"]["req_ds"]},
    )

    sessions = [
        ScheduledSession(
            requirement_id="req_ds", cohort_section_id="sec_a", subject_id="sub_ds",
            teacher_id="tch_1", room_id="rm_lh1", time_slot_id="ts_break", day_of_week=1, period_number=4,
        ),
    ]

    res = validator.validate(sessions)
    assert res.is_valid is False
    assert any("Operating Hours Violation" in v for v in res.hard_violations)
