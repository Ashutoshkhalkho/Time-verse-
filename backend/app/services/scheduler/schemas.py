import enum
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class SolverStatusEnum(str, enum.Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIME_LIMIT = "TIME_LIMIT"
    MODEL_INVALID = "MODEL_INVALID"


@dataclass(frozen=True)
class TimeSlotInput:
    id: str
    day_of_week: int  # 1=Mon, 5=Fri, 6=Sat
    period_number: int  # 1 to 10
    is_break: bool = False
    start_time: str = ""
    end_time: str = ""


@dataclass(frozen=True)
class TeacherScheduleInput:
    id: str
    name: str
    max_hours_per_day: int = 5
    max_consecutive_hours: int = 3
    max_weekly_hours: int = 20
    unavailable_slot_ids: frozenset[str] = field(default_factory=frozenset)
    # slot_id -> weight (-2 avoid, +2 preferred)
    preference_weights: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RoomScheduleInput:
    id: str
    building: str
    room_number: str
    capacity: int
    room_type: str  # LECTURE_HALL, COMPUTER_LAB, etc.
    is_active: bool = True


@dataclass(frozen=True)
class CohortSectionInput:
    id: str
    department_id: str
    section_name: str
    student_count: int


@dataclass(frozen=True)
class SubjectRequirementInput:
    id: str
    cohort_section_id: str
    subject_id: str
    subject_code: str
    subject_name: str
    subject_type: str  # THEORY, LABORATORY, etc.
    teacher_id: str
    required_room_type: str  # LECTURE_HALL, COMPUTER_LAB, etc.
    required_sessions_per_week: int
    duration_periods: int = 1
    requires_consecutive_periods: bool = False
    preferred_room_id: str | None = None


@dataclass
class SchedulingConfig:
    time_limit_seconds: float = 30.0
    weight_preferred_times: int = 10
    weight_balanced_daily_workload: int = 15
    weight_minimize_gaps: int = 10
    max_daily_sessions_per_teacher: int = 5
    max_daily_sessions_per_cohort: int = 6


@dataclass(frozen=True)
class LockedSessionInput:
    requirement_id: str | None = None
    cohort_section_id: str | None = None
    subject_id: str | None = None
    teacher_id: str | None = None
    room_id: str = ""
    time_slot_id: str = ""
    day_of_week: int | None = None
    period_number: int | None = None


@dataclass
class ScheduledSession:
    requirement_id: str
    cohort_section_id: str
    subject_id: str
    teacher_id: str
    room_id: str
    time_slot_id: str
    day_of_week: int
    period_number: int
    is_locked: bool = False


@dataclass
class SolverResult:
    status: SolverStatusEnum
    wall_time_seconds: float
    objective_value: float | None
    sessions: list[ScheduledSession] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    is_valid: bool
    hard_violations: list[str] = field(default_factory=list)
    soft_warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class GenerateScheduleRequest(BaseModel):
    department_id: str = Field(..., description="Target department ID")
    academic_term_id: str = Field(..., description="Target academic term ID")
    time_limit_seconds: float = Field(30.0, ge=5.0, le=300.0, description="Solver execution timeout in seconds")
    weight_preferred_times: int = Field(10, ge=0, le=100)
    weight_balanced_daily_workload: int = Field(15, ge=0, le=100)
    weight_minimize_gaps: int = Field(10, ge=0, le=100)
    notes: str | None = Field(None, description="Optional coordinator notes")


class GenerateScheduleResponse(BaseModel):
    timetable_id: str
    status: str
    solver_status: str
    is_valid: bool
    wall_time_seconds: float
    total_sessions_scheduled: int
    hard_violations: list[str]
    soft_warnings: list[str]
    diagnostics: list[str]
