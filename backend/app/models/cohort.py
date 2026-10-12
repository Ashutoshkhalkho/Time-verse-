from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import AcademicTerm, Department
    from app.models.user import StudentEnrollment, User


class CohortSection(Base, TimestampMixin):
    __tablename__ = "cohort_sections"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    department_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    academic_term_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    program_name: Mapped[str] = mapped_column(String(100), nullable=False)
    year_level: Mapped[int] = mapped_column(Integer, nullable=False)
    section_name: Mapped[str] = mapped_column(String(20), nullable=False)
    student_count: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    cr_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    department: Mapped["Department"] = relationship("Department")
    academic_term: Mapped["AcademicTerm"] = relationship("AcademicTerm")
    cr_user: Mapped["User | None"] = relationship("User", foreign_keys=[cr_user_id])
    enrollments: Mapped[list["StudentEnrollment"]] = relationship(
        "StudentEnrollment", back_populates="cohort_section", cascade="all, delete-orphan"
    )
