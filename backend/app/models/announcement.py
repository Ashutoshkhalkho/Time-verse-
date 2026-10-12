import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin
from app.models.alert import AlertSeverityEnum

if TYPE_CHECKING:
    from app.models.organization import Department
    from app.models.user import User


class AnnouncementCategoryEnum(str, enum.Enum):
    ACADEMIC_NOTICE = "ACADEMIC_NOTICE"
    TIMETABLE_CHANGE = "TIMETABLE_CHANGE"
    EXAMINATION = "EXAMINATION"
    INSTITUTIONAL = "INSTITUTIONAL"
    EMERGENCY = "EMERGENCY"


class AnnouncementTargetAudienceEnum(str, enum.Enum):
    ALL = "ALL"
    STUDENTS = "STUDENTS"
    FACULTY = "FACULTY"
    STAFF = "STAFF"


class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[AnnouncementCategoryEnum] = mapped_column(
        Enum(AnnouncementCategoryEnum, name="announcement_category_enum", native_enum=False),
        default=AnnouncementCategoryEnum.ACADEMIC_NOTICE,
        nullable=False,
    )
    severity: Mapped[AlertSeverityEnum] = mapped_column(
        Enum(AlertSeverityEnum, name="alert_severity_enum", native_enum=False),
        default=AlertSeverityEnum.INFORMATIONAL,
        nullable=False,
    )
    target_audience: Mapped[AnnouncementTargetAudienceEnum] = mapped_column(
        Enum(AnnouncementTargetAudienceEnum, name="announcement_target_enum", native_enum=False),
        default=AnnouncementTargetAudienceEnum.ALL,
        nullable=False,
    )
    department_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    author_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    author: Mapped["User"] = relationship("User")
    department: Mapped["Department | None"] = relationship("Department")
