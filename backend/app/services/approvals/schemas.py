from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.change_request import ChangeRequestTypeEnum, RequestStatusEnum


class ChangeRequestCreate(BaseModel):
    timetable_id: str
    target_session_id: str
    request_type: ChangeRequestTypeEnum
    reason: str
    proposed_time_slot_id: str | None = None
    proposed_room_id: str | None = None
    proposed_teacher_id: str | None = None


class ChangeRequestDecision(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    decision_reason: str
    selected_alternative_id: str | None = None
    expected_lock_version: int | None = None


class ChangeRequestAlternativeResponse(BaseModel):
    id: str
    option_rank: int
    proposed_time_slot_id: str
    proposed_time_slot_name: str
    proposed_room_id: str
    proposed_room_number: str
    proposed_teacher_id: str
    proposed_teacher_name: str
    affected_sessions_count: int
    soft_penalty_score: float
    trade_off_explanation: dict[str, Any] | None
    is_selected: bool


class ChangeRequestResponse(BaseModel):
    id: str
    timetable_id: str
    target_session_id: str
    requester_user_id: str
    requester_name: str
    request_type: ChangeRequestTypeEnum
    reason: str
    status: RequestStatusEnum
    proposed_time_slot_id: str | None
    proposed_room_id: str | None
    proposed_teacher_id: str | None
    reviewer_user_id: str | None
    reviewer_name: str | None
    review_decision_reason: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    alternatives: list[ChangeRequestAlternativeResponse] = Field(default_factory=list)


class SessionDiffDetail(BaseModel):
    session_id: str
    subject_code: str
    subject_name: str
    cohort_name: str
    teacher_name: str
    room_number: str
    time_slot_name: str
    diff_type: str  # "ADDED", "REMOVED", "MODIFIED", "UNCHANGED"
    prior_time_slot_name: str | None = None
    prior_room_number: str | None = None
    prior_teacher_name: str | None = None


class VersionCompareResponse(BaseModel):
    version_a_id: str
    version_a_label: str
    version_b_id: str
    version_b_label: str
    total_sessions_a: int
    total_sessions_b: int
    added_count: int
    removed_count: int
    modified_count: int
    unchanged_count: int
    session_diffs: list[SessionDiffDetail]


class RollbackRequest(BaseModel):
    target_version_id: str
    reason: str
