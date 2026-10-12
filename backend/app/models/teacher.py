from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.infrastructure import TimeSlot
    from app.models.organization import Department
    from app.models.user import User


class Teacher(Base, TimestampMixin):
    __tablename__ = "teachers"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    department_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False)
    max_hours_per_day: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_consecutive_hours: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_weekly_hours: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    user: Mapped["User"] = relationship("User")
    department: Mapped["Department"] = relationship("Department")
    availabilities: Mapped[list["TeacherAvailability"]] = relationship(
        "TeacherAvailability", back_populates="teacher", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        from sqlalchemy import inspect
        state = inspect(self)
        if "user" in state.unloaded:
            return self.employee_code
        return self.user.full_name if self.user else self.employee_code



class TeacherAvailability(Base, TimestampMixin):
    __tablename__ = "teacher_availabilities"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    teacher_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_slot_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preference_weight: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # -2: Avoid, 0: Neutral, +2: Preferred
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="availabilities")
    time_slot: Mapped["TimeSlot"] = relationship("TimeSlot")
