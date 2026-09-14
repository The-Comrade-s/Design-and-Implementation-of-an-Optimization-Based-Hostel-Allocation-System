from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, ValidationError
from app.models.hostel import HostelCategory, RoomType
from app.services import hostel_service


def _make_room(session, capacity=4):
    hostel = hostel_service.create_hostel(session, name="Hostel A", code="H-A", category=HostelCategory.MIXED)
    block = hostel_service.create_block(session, hostel_id=hostel.id, name="Block A", code="A1")
    floor = hostel_service.create_floor(session, block_id=block.id, name="1")
    room = hostel_service.create_room(session, floor_id=floor.id, room_number="A101",
                                       room_type=RoomType.FOUR_PERSON, capacity=capacity)
    return hostel, block, floor, room


def test_create_hostel_and_duplicate_code_rejected(session):
    hostel_service.create_hostel(session, name="Hostel A", code="H-A", category=HostelCategory.MIXED)
    with pytest.raises(ConflictError):
        hostel_service.create_hostel(session, name="Hostel A2", code="H-A", category=HostelCategory.MIXED)


def test_room_generates_correct_bed_count(session):
    _, _, _, room = _make_room(session, capacity=4)
    assert len(room.bed_spaces) == 4


def test_duplicate_room_number_rejected(session):
    hostel, block, floor, _ = _make_room(session)
    with pytest.raises(ConflictError):
        hostel_service.create_room(session, floor_id=floor.id, room_number="A101",
                                    room_type=RoomType.DOUBLE, capacity=2)


def test_invalid_capacity_rejected(session):
    hostel = hostel_service.create_hostel(session, name="Hostel B", code="H-B", category=HostelCategory.MIXED)
    block = hostel_service.create_block(session, hostel_id=hostel.id, name="Block B", code="B1")
    floor = hostel_service.create_floor(session, block_id=block.id, name="1")
    with pytest.raises(ValidationError):
        hostel_service.create_room(session, floor_id=floor.id, room_number="B101",
                                    room_type=RoomType.SINGLE, capacity=0)


def test_regenerating_beds_does_not_delete_existing(session):
    _, _, _, room = _make_room(session, capacity=2)
    assert len(room.bed_spaces) == 2
    room.capacity = 4
    session.flush()
    hostel_service.generate_bed_spaces_for_room(session, room)
    assert len(room.bed_spaces) == 4


def test_usable_bed_count_excludes_inactive(session):
    from app.models.hostel import AccommodationStatus, BedStatus
    hostel, block, floor, room = _make_room(session, capacity=2)
    assert hostel_service.usable_bed_count(session) == 2
    bed = room.bed_spaces[0]
    hostel_service.update_bed_status(session, bed.id, BedStatus.MAINTENANCE)
    assert hostel_service.usable_bed_count(session) == 1
    hostel_service.update_hostel_status(session, hostel.id, AccommodationStatus.INACTIVE)
    assert hostel_service.usable_bed_count(session) == 0
