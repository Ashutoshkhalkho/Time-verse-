import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.cohort import CohortSection


class UserRoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    HOD = "HOD"
    COORDINATOR = "COORDINATOR"
    TEACHER = "TEACHER"
    CR = "CR"
    STUDENT = "STUDENT"
    MENTOR = "MENTOR"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    institution_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role: Mapped[UserRoleEnum] = mapped_column(
        Enum(UserRoleEnum, name="user_role_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notification_preferences: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=lambda: {"in_app": True, "email": True},
        nullable=False,
    )

    department_scopes: Mapped[list["UserDepartmentScope"]] = relationship(
        "UserDepartmentScope", back_populates="user", cascade="all, delete-orphan"
    )
    student_enrollments: Mapped[list["StudentEnrollment"]] = relationship(
        "StudentEnrollment", back_populates="student_user", cascade="all, delete-orphan"
    )
    mentee_assignments: Mapped[list["MentorAssignment"]] = relationship(
        "MentorAssignment",
        foreign_keys="MentorAssignment.mentor_user_id",
        back_populates="mentor_user",
        cascade="all, delete-orphan",
    )


class UserDepartmentScope(Base, TimestampMixin):
    __tablename__ = "user_department_scopes"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="department_scopes")


class StudentEnrollment(Base, TimestampMixin):
    __tablename__ = "student_enrollments"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    student_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cohort_section_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("cohort_sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    student_user: Mapped["User"] = relationship("User", back_populates="student_enrollments")
    cohort_section: Mapped["CohortSection"] = relationship(
        "CohortSection", back_populates="enrollments"
    )


class MentorAssignment(Base, TimestampMixin):
    __tablename__ = "mentor_assignments"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    mentor_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    mentor_user: Mapped["User"] = relationship(
        "User", foreign_keys=[mentor_user_id], back_populates="mentee_assignments"
    )
    student_user: Mapped["User"] = relationship("User", foreign_keys=[student_user_id])


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    jti: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    token_type: Mapped[str] = mapped_column(String(20), default="access", nullable=False)
    user_id: Mapped[str] = mapped_column(String(26), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
