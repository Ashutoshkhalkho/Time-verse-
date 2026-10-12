import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.infrastructure import Room, TimeSlot
    from app.models.teacher import Teacher
    from app.models.timetable import Timetable, TimetableSession
    from app.models.user import User


class RequestStatusEnum(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ALTERNATIVES_PROPOSED = "ALTERNATIVES_PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ChangeRequestTypeEnum(str, enum.Enum):
    RESCHEDULE_SESSION = "RESCHEDULE_SESSION"
    SWAP_ROOM = "SWAP_ROOM"
    SUBSTITUTE_TEACHER = "SUBSTITUTE_TEACHER"
    CANCEL_SESSION = "CANCEL_SESSION"


class ChangeRequest(Base, TimestampMixin):
    __tablename__ = "change_requests"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    timetable_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("timetables.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target_session_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("timetable_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requester_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    request_type: Mapped[ChangeRequestTypeEnum] = mapped_column(
        Enum(ChangeRequestTypeEnum, name="change_request_type_enum", native_enum=False),
        nullable=False,
    )
    proposed_time_slot_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("time_slots.id", ondelete="SET NULL"), nullable=True
    )
    proposed_room_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True
    )
    proposed_teacher_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RequestStatusEnum] = mapped_column(
        Enum(RequestStatusEnum, name="request_status_enum", native_enum=False),
        default=RequestStatusEnum.SUBMITTED,
        nullable=False,
        index=True,
    )
    reviewer_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    timetable: Mapped["Timetable"] = relationship("Timetable")
    target_session: Mapped["TimetableSession"] = relationship("TimetableSession")
    requester: Mapped["User"] = relationship("User", foreign_keys=[requester_user_id])
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewer_user_id])
    proposed_time_slot: Mapped["TimeSlot | None"] = relationship("TimeSlot")
    proposed_room: Mapped["Room | None"] = relationship("Room")
    proposed_teacher: Mapped["Teacher | None"] = relationship("Teacher")

    alternatives: Mapped[list["ChangeRequestAlternative"]] = relationship(
        "ChangeRequestAlternative", back_populates="change_request", cascade="all, delete-orphan"
    )


class ChangeRequestAlternative(Base, TimestampMixin):
    __tablename__ = "change_request_alternatives"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    change_request_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("change_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_time_slot_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("time_slots.id", ondelete="RESTRICT"), nullable=False
    )
    proposed_room_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False
    )
    proposed_teacher_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False
    )
    affected_sessions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    soft_penalty_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    trade_off_explanation: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    change_request: Mapped["ChangeRequest"] = relationship("ChangeRequest", back_populates="alternatives")
    proposed_time_slot: Mapped["TimeSlot"] = relationship("TimeSlot")
    proposed_room: Mapped["Room"] = relationship("Room")
    proposed_teacher: Mapped["Teacher"] = relationship("Teacher")
