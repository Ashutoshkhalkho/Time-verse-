import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.cohort import CohortSection
    from app.models.curriculum import Subject
    from app.models.infrastructure import Room, TimeSlot
    from app.models.teacher import Teacher


class TimetableStatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"
    SIMULATED = "SIMULATED"
    PROPOSED = "PROPOSED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class SessionStatusEnum(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    TENTATIVE = "TENTATIVE"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"


class Timetable(Base, TimestampMixin):
    __tablename__ = "timetables"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    department_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    academic_term_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False
    )
    version_major: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    version_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("timetables.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[TimetableStatusEnum] = mapped_column(
        Enum(TimetableStatusEnum, name="timetable_status_enum", native_enum=False),
        default=TimetableStatusEnum.DRAFT,
        nullable=False,
        index=True,
    )
    solver_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    solver_score: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    sessions: Mapped[list["TimetableSession"]] = relationship(
        "TimetableSession", back_populates="timetable", cascade="all, delete-orphan"
    )
    parent_version: Mapped["Timetable | None"] = relationship(
        "Timetable", remote_side=[id], backref="child_versions"
    )


class TimetableSession(Base, TimestampMixin):
    __tablename__ = "timetable_sessions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    timetable_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("timetables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("subject_requirements.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cohort_section_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("cohort_sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    teacher_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    room_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    time_slot_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("time_slots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[SessionStatusEnum] = mapped_column(
        Enum(SessionStatusEnum, name="session_status_enum", native_enum=False),
        default=SessionStatusEnum.OFFICIAL,
        nullable=False,
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    timetable: Mapped["Timetable"] = relationship("Timetable", back_populates="sessions")
    cohort_section: Mapped["CohortSection"] = relationship("CohortSection")
    subject: Mapped["Subject"] = relationship("Subject")
    teacher: Mapped["Teacher"] = relationship("Teacher")
    room: Mapped["Room"] = relationship("Room")
    time_slot: Mapped["TimeSlot"] = relationship("TimeSlot")

