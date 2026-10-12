import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin


class RoomTypeEnum(str, enum.Enum):
    LECTURE_HALL = "LECTURE_HALL"
    COMPUTER_LAB = "COMPUTER_LAB"
    SCIENCE_LAB = "SCIENCE_LAB"
    SEMINAR_ROOM = "SEMINAR_ROOM"
    WORKSHOP = "WORKSHOP"


class Room(Base, TimestampMixin):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    institution_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    building: Mapped[str] = mapped_column(String(100), nullable=False)
    room_number: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type: Mapped[RoomTypeEnum] = mapped_column(
        Enum(RoomTypeEnum, name="room_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    equipment: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=list,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def is_lab(self) -> bool:
        return self.room_type in {
            RoomTypeEnum.COMPUTER_LAB,
            RoomTypeEnum.SCIENCE_LAB,
            RoomTypeEnum.WORKSHOP,
        }



class TimeSlot(Base, TimestampMixin):
    __tablename__ = "time_slots"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    institution_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # 1=Mon, 6=Sat
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[Time] = mapped_column(Time, nullable=False)
    end_time: Mapped[Time] = mapped_column(Time, nullable=False)
    is_break: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
