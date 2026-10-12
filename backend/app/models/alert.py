import enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class AlertSeverityEnum(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFORMATIONAL = "INFORMATIONAL"


class AlertCategoryEnum(str, enum.Enum):
    CONFLICT = "CONFLICT"
    TIMETABLE_CHANGE = "TIMETABLE_CHANGE"
    EMERGENCY = "EMERGENCY"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    OFFICIAL_BROADCAST = "OFFICIAL_BROADCAST"


class AlertResolutionStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    recipient_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[AlertSeverityEnum] = mapped_column(
        Enum(AlertSeverityEnum, name="alert_severity_enum", native_enum=False),
        default=AlertSeverityEnum.INFORMATIONAL,
        nullable=False,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    recipient: Mapped["User"] = relationship("User")

    @property
    def category(self) -> str:
        if self.metadata_json and "category" in self.metadata_json:
            return self.metadata_json["category"]
        if "CLASH" in self.event_type or "CONFLICT" in self.event_type:
            return AlertCategoryEnum.CONFLICT.value
        if "CHANGE" in self.event_type or "RESCHEDULE" in self.event_type or "PUBLISH" in self.event_type:
            return AlertCategoryEnum.TIMETABLE_CHANGE.value
        if "EMERGENCY" in self.event_type or "LEAVE" in self.event_type:
            return AlertCategoryEnum.EMERGENCY.value
        if "ADMIN" in self.event_type or "WORKLOAD" in self.event_type:
            return AlertCategoryEnum.ADMINISTRATIVE.value
        return AlertCategoryEnum.OFFICIAL_BROADCAST.value

    @property
    def resolution_status(self) -> str:
        if self.metadata_json and "resolution_status" in self.metadata_json:
            return self.metadata_json["resolution_status"]
        if self.severity in {AlertSeverityEnum.CRITICAL, AlertSeverityEnum.HIGH}:
            return AlertResolutionStatusEnum.PENDING.value
        return AlertResolutionStatusEnum.RESOLVED.value
