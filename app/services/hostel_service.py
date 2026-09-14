from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.hostel import (
    AccommodationStatus, BedSpace, BedStatus, Block, Floor, Hostel, HostelCategory, Room, RoomType,
)
from app.services.audit_service import log_action


# ---- Hostel ----

def create_hostel(session: Session, *, name: str, code: str, category: HostelCategory,
                   description: str | None = None, location: str | None = None,
                   actor_id: int | None = None) -> Hostel:
    if not name or not code:
        raise ValidationError("Hostel name and code are required.")
    existing = session.scalars(select(Hostel).where(Hostel.code == code)).first()
    if existing:
        raise ConflictError(f"A hostel with code '{code}' already exists.")
    hostel = Hostel(name=name, code=code, category=category, description=description, location=location)
    session.add(hostel)
    session.flush()
    log_action(session, user_id=actor_id, action="HOSTEL_CREATED", entity_type="Hostel", entity_id=hostel.id)
    return hostel


def update_hostel_status(session: Session, hostel_id: int, status: AccommodationStatus, actor_id: int | None = None) -> Hostel:
    hostel = session.get(Hostel, hostel_id)
    if not hostel:
        raise NotFoundError("Hostel not found.")
    hostel.status = status
    session.flush()
    log_action(session, user_id=actor_id, action="HOSTEL_UPDATED", entity_type="Hostel", entity_id=hostel.id)
    return hostel


def list_hostels(session: Session, *, status: AccommodationStatus | None = None,
                  category: HostelCategory | None = None) -> list[Hostel]:
    stmt = select(Hostel)
    if status:
        stmt = stmt.where(Hostel.status == status)
    if category:
        stmt = stmt.where(Hostel.category == category)
    return list(session.scalars(stmt.order_by(Hostel.name)).all())


# ---- Block ----

def create_block(session: Session, *, hostel_id: int, name: str, code: str,
                  description: str | None = None, actor_id: int | None = None) -> Block:
    hostel = session.get(Hostel, hostel_id)
    if not hostel:
        raise NotFoundError("Hostel not found.")
    existing = session.scalars(
        select(Block).where(Block.hostel_id == hostel_id, Block.code == code)
    ).first()
    if existing:
        raise ConflictError(f"Block code '{code}' already exists in this hostel.")
    block = Block(hostel_id=hostel_id, name=name, code=code, description=description)
    session.add(block)
    session.flush()
    log_action(session, user_id=actor_id, action="BLOCK_CREATED", entity_type="Block", entity_id=block.id)
    return block


# ---- Floor ----

def create_floor(session: Session, *, block_id: int, name: str, description: str | None = None,
                  actor_id: int | None = None) -> Floor:
    block = session.get(Block, block_id)
    if not block:
        raise NotFoundError("Block not found.")
    existing = session.scalars(select(Floor).where(Floor.block_id == block_id, Floor.name == name)).first()
    if existing:
        raise ConflictError(f"Floor '{name}' already exists in this block.")
    floor = Floor(block_id=block_id, name=name, description=description)
    session.add(floor)
    session.flush()
    log_action(session, user_id=actor_id, action="FLOOR_CREATED", entity_type="Floor", entity_id=floor.id)
    return floor


# ---- Room (+ automatic bed-space generation) ----

def create_room(session: Session, *, floor_id: int, room_number: str, room_type: RoomType,
                 capacity: int, description: str | None = None, generate_beds: bool = True,
                 actor_id: int | None = None) -> Room:
    floor = session.get(Floor, floor_id)
    if not floor:
        raise NotFoundError("Floor not found.")
    if capacity <= 0:
        raise ValidationError("Room capacity must be greater than zero.")
    existing = session.scalars(select(Room).where(Room.floor_id == floor_id, Room.room_number == room_number)).first()
    if existing:
        raise ConflictError(f"Room number '{room_number}' already exists on this floor.")

    room = Room(floor_id=floor_id, room_number=room_number, room_type=room_type,
                capacity=capacity, description=description)
    session.add(room)
    session.flush()
    log_action(session, user_id=actor_id, action="ROOM_CREATED", entity_type="Room", entity_id=room.id)

    if generate_beds:
        generate_bed_spaces_for_room(session, room, actor_id=actor_id)
    return room


def generate_bed_spaces_for_room(session: Session, room: Room, actor_id: int | None = None) -> list[BedSpace]:
    """Create bed spaces up to room.capacity, without deleting existing beds."""
    existing_count = session.scalar(
        select(func.count()).select_from(BedSpace).where(BedSpace.room_id == room.id)
    ) or 0
    created = []
    for i in range(existing_count + 1, room.capacity + 1):
        bed = BedSpace(room_id=room.id, bed_identifier=f"{room.room_number}-B{i:02d}")
        session.add(bed)
        created.append(bed)
    session.flush()
    if created:
        session.expire(room, ["bed_spaces"])
        log_action(session, user_id=actor_id, action="BED_CREATED", entity_type="Room", entity_id=room.id,
                    description=f"Generated {len(created)} bed space(s)")
    return created


def update_bed_status(session: Session, bed_id: int, status: BedStatus, actor_id: int | None = None) -> BedSpace:
    bed = session.get(BedSpace, bed_id)
    if not bed:
        raise NotFoundError("Bed space not found.")
    bed.status = status
    session.flush()
    log_action(session, user_id=actor_id, action="BED_UPDATED", entity_type="BedSpace", entity_id=bed.id)
    return bed


# ---- Capacity / usable accommodation ----

def usable_bed_count(session: Session, academic_session: str | None = None) -> int:
    """Count beds that are AVAILABLE and belong to ACTIVE room/floor/block/hostel."""
    stmt = (
        select(func.count())
        .select_from(BedSpace)
        .join(Room, BedSpace.room_id == Room.id)
        .join(Floor, Room.floor_id == Floor.id)
        .join(Block, Floor.block_id == Block.id)
        .join(Hostel, Block.hostel_id == Hostel.id)
        .where(
            BedSpace.status == BedStatus.AVAILABLE,
            Room.status == AccommodationStatus.ACTIVE,
            Floor.status == AccommodationStatus.ACTIVE,
            Block.status == AccommodationStatus.ACTIVE,
            Hostel.status == AccommodationStatus.ACTIVE,
        )
    )
    return session.scalar(stmt) or 0


def total_bed_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(BedSpace)) or 0


def hostel_capacity_overview(session: Session) -> list[dict]:
    """Return per-hostel capacity/usable/status counts for dashboards & reports."""
    hostels = list(session.scalars(select(Hostel).order_by(Hostel.name)).all())
    overview = []
    for h in hostels:
        beds_stmt = (
            select(BedSpace.status, func.count())
            .select_from(BedSpace)
            .join(Room, BedSpace.room_id == Room.id)
            .join(Floor, Room.floor_id == Floor.id)
            .join(Block, Floor.block_id == Block.id)
            .where(Block.hostel_id == h.id)
            .group_by(BedSpace.status)
        )
        counts = {status.value: 0 for status in BedStatus}
        for status, count in session.execute(beds_stmt).all():
            counts[status.value] = count
        total = sum(counts.values())
        usable = counts.get(BedStatus.AVAILABLE.value, 0) if h.status == AccommodationStatus.ACTIVE else 0
        overview.append({
            "hostel": h.name,
            "code": h.code,
            "status": h.status.value,
            "total_capacity": total,
            "usable_capacity": usable,
            "blocked": counts.get(BedStatus.BLOCKED.value, 0),
            "maintenance": counts.get(BedStatus.MAINTENANCE.value, 0),
        })
    return overview
