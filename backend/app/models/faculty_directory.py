import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ProfileStatusEnum(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


def generate_directory_id() -> str:
    return f"fac_{uuid.uuid4().hex[:16]}"


class FacultyDirectoryMember(Base, TimestampMixin):
    """
    Faculty Directory Member for Kristu Jayanti University (KJU),
    Department of Professional Management Studies (DPMS).
    
    Preserves exact supplied names, tracks public source citations,
    and requires verified confirmation before formal academic designations
    are certified by an authorized administrator.
    """
    __tablename__ = "faculty_directory_members"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_directory_id,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Department of Professional Management Studies",
    )
    institution: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Kristu Jayanti University",
    )
    faculty_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=False)
    official_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_photo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subjects_taught: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    specialisation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    office_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    profile_status: Mapped[ProfileStatusEnum] = mapped_column(
        String(30),
        nullable=False,
        default=ProfileStatusEnum.PENDING_VERIFICATION,
        index=True,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    source_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    verified_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    potential_duplicate_of_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    verified_by: Mapped[Any | None] = relationship("User", foreign_keys=[verified_by_user_id], lazy="selectin")

    __table_args__ = (
        Index("ix_fac_dir_dept_status", "department", "profile_status"),
        Index("ix_fac_dir_archived", "archived_at"),
    )
