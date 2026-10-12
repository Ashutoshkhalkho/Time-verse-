import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.infrastructure import RoomTypeEnum

if TYPE_CHECKING:
    from app.models.cohort import CohortSection
    from app.models.infrastructure import Room
    from app.models.organization import Department
    from app.models.teacher import Teacher


class SubjectTypeEnum(str, enum.Enum):
    THEORY = "THEORY"
    LABORATORY = "LABORATORY"
    SEMINAR = "SEMINAR"
    PROJECT = "PROJECT"


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    department_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    subject_type: Mapped[SubjectTypeEnum] = mapped_column(
        Enum(SubjectTypeEnum, name="subject_type_enum", native_enum=False),
        default=SubjectTypeEnum.THEORY,
        nullable=False,
    )
    required_room_type: Mapped[RoomTypeEnum] = mapped_column(
        Enum(RoomTypeEnum, name="room_type_enum", native_enum=False),
        default=RoomTypeEnum.LECTURE_HALL,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    department: Mapped["Department"] = relationship("Department")


class SubjectRequirement(Base, TimestampMixin):
    __tablename__ = "subject_requirements"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    cohort_section_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("cohort_sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    teacher_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    required_sessions_per_week: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    duration_periods: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    requires_consecutive_periods: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferred_room_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True
    )

    cohort_section: Mapped["CohortSection"] = relationship("CohortSection")
    subject: Mapped["Subject"] = relationship("Subject")
    teacher: Mapped["Teacher"] = relationship("Teacher")
    preferred_room: Mapped["Room | None"] = relationship("Room")
