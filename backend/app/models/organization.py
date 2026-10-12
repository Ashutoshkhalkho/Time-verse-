from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class Institution(Base, TimestampMixin):
    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    operating_hours: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=lambda: {"start": "08:30", "end": "16:30", "days": [1, 2, 3, 4, 5, 6]},
        nullable=False,
    )

    departments: Mapped[list["Department"]] = relationship(
        "Department", back_populates="institution", cascade="all, delete-orphan"
    )


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    institution_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    hod_user_id: Mapped[str | None] = mapped_column(String(26), nullable=True)

    institution: Mapped["Institution"] = relationship("Institution", back_populates="departments")


class AcademicTerm(Base, TimestampMixin):
    __tablename__ = "academic_terms"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    institution_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
