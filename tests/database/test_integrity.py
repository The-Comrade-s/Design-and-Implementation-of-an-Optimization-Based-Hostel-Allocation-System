from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.hostel import BedSpace, Hostel, HostelCategory, Room, RoomType
from app.services import hostel_service


def test_hostel_code_unique_at_db_level(session):
    hostel_service.create_hostel(session, name="Hostel A", code="H-A", category=HostelCategory.MIXED)
    session.add(Hostel(name="Hostel A2", code="H-A", category=HostelCategory.MIXED))
    with pytest.raises(IntegrityError):
        session.flush()


def test_bed_identifier_unique_within_room(session):
    hostel = hostel_service.create_hostel(session, name="Hostel A", code="H-A", category=HostelCategory.MIXED)
    block = hostel_service.create_block(session, hostel_id=hostel.id, name="Block A", code="A1")
    floor = hostel_service.create_floor(session, block_id=block.id, name="1")
    room = hostel_service.create_room(session, floor_id=floor.id, room_number="A101",
                                       room_type=RoomType.SINGLE, capacity=1, generate_beds=True)
    session.add(BedSpace(room_id=room.id, bed_identifier=room.bed_spaces[0].bed_identifier))
    with pytest.raises(IntegrityError):
        session.flush()
