from typing import Any

from pydantic import BaseModel, Field


class SimulationScenarioRequest(BaseModel):
    timetable_id: str
    target_session_id: str | None = None
    proposed_time_slot_id: str | None = None
    proposed_room_id: str | None = None
    proposed_teacher_id: str | None = None
    unavailable_room_id: str | None = None
    unavailable_teacher_id: str | None = None
    affected_time_slot_ids: list[str] | None = None
    reason: str | None = "Impact Analysis Simulation"


class AffectedSessionDetail(BaseModel):
    session_id: str
    subject_code: str
    subject_name: str
    cohort_name: str
    teacher_name: str
    room_number: str
    current_time_slot_id: str
    current_time_slot_name: str
    conflict_reason: str
    is_directly_affected: bool


class AlternativeOption(BaseModel):
    option_rank: int
    proposed_time_slot_id: str
    proposed_time_slot_name: str
    proposed_room_id: str
    proposed_room_number: str
    proposed_teacher_id: str
    proposed_teacher_name: str
    affected_sessions_count: int = 0
    soft_penalty_score: float = 0.0
    trade_off_explanation: dict[str, Any] = Field(default_factory=dict)
    is_feasible: bool = True


class SimulationReport(BaseModel):
    timetable_id: str
    scenario_summary: str
    is_feasible: bool
    directly_affected_count: int
    indirectly_affected_count: int
    affected_sessions: list[AffectedSessionDetail]
    alternatives: list[AlternativeOption]
    diagnostics: list[str]
