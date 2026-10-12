from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import Department


class SchedulingPreference(Base, TimestampMixin):
    __tablename__ = "scheduling_preferences"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    department_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("departments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    weight_preferred_times: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    weight_balanced_daily_workload: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    weight_minimize_gaps: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_daily_sessions_per_teacher: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_daily_sessions_per_cohort: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    custom_rules: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )

    department: Mapped["Department"] = relationship("Department")
