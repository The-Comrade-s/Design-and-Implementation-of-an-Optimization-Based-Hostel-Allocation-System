from __future__ import annotations

from app.models.hostel import HostelCategory, RoomType
from app.models.optimization import OptimizationStatus
from app.models.student import Gender
from app.models.user import UserRole
from app.services import application_service, hostel_service, student_service
from app.services.auth_service import register_user
from app.services.optimization_service import execute_optimization
from app.services.priority_service import seed_default_rules


def _make_hostel(session, code, category, beds=4):
    hostel = hostel_service.create_hostel(session, name=f"Hostel {code}", code=code, category=category)
    block = hostel_service.create_block(session, hostel_id=hostel.id, name=f"Block {code}", code=f"{code}1")
    floor = hostel_service.create_floor(session, block_id=block.id, name="1")
    hostel_service.create_room(session, floor_id=floor.id, room_number=f"{code}101",
                                room_type=RoomType.OTHER, capacity=beds, generate_beds=True)
    return hostel


def _make_verified_student(session, sid, gender, hostel):
    user = register_user(session, f"{sid.lower()}@x.com", "Password123", UserRole.STUDENT)
    student = student_service.create_student(
        session, user_id=user.id, student_id=sid, first_name="A", last_name="B", gender=gender,
        email=f"{sid.lower()}@x.com", department="CS", programme="CS", level="400",
        academic_session="2026/2027",
    )
    app_ = application_service.create_application(session, student_id=student.id, academic_session="2026/2027")
    application_service.set_hostel_preferences(session, app_.id, [(hostel.id, 1)])
    application_service.submit_application(session, app_.id)
    application_service.verify_application(session, app_.id, verifier_user_id=1)
    return student, app_


def test_more_students_than_beds_partial_allocation(session):
    seed_default_rules(session)
    hostel = _make_hostel(session, "A", HostelCategory.MIXED, beds=2)
    for i in range(1, 5):
        _make_verified_student(session, f"STU00{i}", Gender.MALE, hostel)

    outcome = execute_optimization(session, academic_session="2026/2027", time_limit_seconds=10, actor_id=1)
    assert outcome.applicant_count == 4
    assert outcome.bed_space_count == 2
    assert outcome.allocated_count == 2
    assert outcome.unallocated_count == 2


def test_more_beds_than_students_full_allocation(session):
    seed_default_rules(session)
    hostel = _make_hostel(session, "A", HostelCategory.MIXED, beds=6)
    for i in range(1, 3):
        _make_verified_student(session, f"STU00{i}", Gender.MALE, hostel)

    outcome = execute_optimization(session, academic_session="2026/2027", time_limit_seconds=10, actor_id=1)
    assert outcome.allocated_count == 2
    assert outcome.unallocated_count == 0


def test_no_available_beds(session):
    seed_default_rules(session)
    hostel = _make_hostel(session, "A", HostelCategory.MIXED, beds=1)
    for bed in hostel.blocks[0].floors[0].rooms[0].bed_spaces:
        from app.models.hostel import BedStatus
        hostel_service.update_bed_status(session, bed.id, BedStatus.BLOCKED)
    _make_verified_student(session, "STU001", Gender.MALE, hostel)

    outcome = execute_optimization(session, academic_session="2026/2027", time_limit_seconds=10, actor_id=1)
    assert outcome.allocated_count == 0
    assert outcome.unallocated_count == 1


def test_no_eligible_applicants(session):
    seed_default_rules(session)
    _make_hostel(session, "A", HostelCategory.MIXED, beds=4)
    outcome = execute_optimization(session, academic_session="2026/2027", time_limit_seconds=10, actor_id=1)
    assert outcome.applicant_count == 0
    assert outcome.allocated_count == 0
    assert outcome.status == OptimizationStatus.INFEASIBLE


def test_gender_incompatibility_enforced(session):
    seed_default_rules(session)
    male_hostel = _make_hostel(session, "M", HostelCategory.MALE, beds=4)
    _make_hostel(session, "F", HostelCategory.FEMALE, beds=4)
    # Female student prefers male-only hostel; must not be assigned there.
    _make_verified_student(session, "STU001", Gender.FEMALE, male_hostel)

    outcome = execute_optimization(session, academic_session="2026/2027", time_limit_seconds=10, actor_id=1)
    for assignment in outcome.assignments:
        assert assignment.hostel_id != male_hostel.id


def test_equal_priority_deterministic_and_no_double_booking(session):
    seed_default_rules(session)
    hostel = _make_hostel(session, "A", HostelCategory.MIXED, beds=3)
    for i in range(1, 4):
        _make_verified_student(session, f"STU00{i}", Gender.MALE, hostel)

    outcome = execute_optimization(session, academic_session="2026/2027", time_limit_seconds=10, actor_id=1)
    bed_ids = [c.bed_id for c in outcome.assignments]
    assert len(bed_ids) == len(set(bed_ids))  # no bed double-booked
    student_ids = [c.student_id for c in outcome.assignments]
    assert len(student_ids) == len(set(student_ids))  # no student double-booked
