from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class HostelCategory(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    MIXED = "MIXED"


class AccommodationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"
    BLOCKED = "BLOCKED"


class RoomType(str, enum.Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    TRIPLE = "TRIPLE"
    FOUR_PERSON = "FOUR_PERSON"
    SIX_PERSON = "SIX_PERSON"
    OTHER = "OTHER"


class BedStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    MAINTENANCE = "MAINTENANCE"
    BLOCKED = "BLOCKED"


class Hostel(Base, TimestampMixin):
    __tablename__ = "hostels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[HostelCategory] = mapped_column(Enum(HostelCategory), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[AccommodationStatus] = mapped_column(
        Enum(AccommodationStatus), default=AccommodationStatus.ACTIVE, nullable=False
    )

    blocks = relationship("Block", back_populates="hostel", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Hostel {self.code}>"


class Block(Base, TimestampMixin):
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("hostel_id", "code", name="uq_block_code_per_hostel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AccommodationStatus] = mapped_column(
        Enum(AccommodationStatus), default=AccommodationStatus.ACTIVE, nullable=False
    )

    hostel = relationship("Hostel", back_populates="blocks")
    floors = relationship("Floor", back_populates="block", cascade="all, delete-orphan")


class Floor(Base, TimestampMixin):
    __tablename__ = "floors"
    __table_args__ = (UniqueConstraint("block_id", "name", name="uq_floor_name_per_block"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    block_id: Mapped[int] = mapped_column(ForeignKey("blocks.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AccommodationStatus] = mapped_column(
        Enum(AccommodationStatus), default=AccommodationStatus.ACTIVE, nullable=False
    )

    block = relationship("Block", back_populates="floors")
    rooms = relationship("Room", back_populates="floor", cascade="all, delete-orphan")


class Room(Base, TimestampMixin):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("floor_id", "room_number", name="uq_room_number_per_floor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    floor_id: Mapped[int] = mapped_column(ForeignKey("floors.id"), nullable=False, index=True)
    room_number: Mapped[str] = mapped_column(String(30), nullable=False)
    room_type: Mapped[RoomType] = mapped_column(Enum(RoomType), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AccommodationStatus] = mapped_column(
        Enum(AccommodationStatus), default=AccommodationStatus.ACTIVE, nullable=False
    )

    floor = relationship("Floor", back_populates="rooms")
    bed_spaces = relationship("BedSpace", back_populates="room", cascade="all, delete-orphan")


class BedSpace(Base, TimestampMixin):
    __tablename__ = "bed_spaces"
    __table_args__ = (UniqueConstraint("room_id", "bed_identifier", name="uq_bed_identifier_per_room"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False, index=True)
    bed_identifier: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[BedStatus] = mapped_column(Enum(BedStatus), default=BedStatus.AVAILABLE, nullable=False)

    room = relationship("Room", back_populates="bed_spaces")
