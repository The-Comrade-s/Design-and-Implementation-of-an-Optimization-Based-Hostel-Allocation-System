from __future__ import annotations

import pytest

from app.core.exceptions import AuthenticationError
from app.models.hostel import HostelCategory
from app.models.student import Gender
from app.models.user import UserRole
from app.services import application_service, hostel_service, student_service
from app.services.auth_service import authenticate, register_user


def test_inactive_user_cannot_authenticate(session):
    user = register_user(session, "inactive@x.com", "Password123", UserRole.STUDENT)
    user.is_active = False
    session.flush()
    with pytest.raises(AuthenticationError):
        authenticate(session, "inactive@x.com", "Password123")


def test_students_have_isolated_applications(session):
    """Two students' applications must never collide or be retrievable
    via the other student's id."""
    hostel = hostel_service.create_hostel(session, name="Hostel A", code="H-A", category=HostelCategory.MIXED)

    user1 = register_user(session, "s1@x.com", "Password123", UserRole.STUDENT)
    student1 = student_service.create_student(
        session, user_id=user1.id, student_id="STU001", first_name="A", last_name="B",
        gender=Gender.MALE, email="s1@x.com", department="CS", programme="CS",
        level="400", academic_session="2026/2027",
    )
    user2 = register_user(session, "s2@x.com", "Password123", UserRole.STUDENT)
    student2 = student_service.create_student(
        session, user_id=user2.id, student_id="STU002", first_name="C", last_name="D",
        gender=Gender.FEMALE, email="s2@x.com", department="CS", programme="CS",
        level="400", academic_session="2026/2027",
    )

    app1 = application_service.create_application(session, student_id=student1.id, academic_session="2026/2027")
    app2 = application_service.create_application(session, student_id=student2.id, academic_session="2026/2027")

    assert app1.id != app2.id
    fetched_for_student2 = application_service.get_student_application(session, student2.id, "2026/2027")
    assert fetched_for_student2.id == app2.id
    assert fetched_for_student2.id != app1.id


def test_password_hash_never_equals_plaintext(session):
    user = register_user(session, "check@x.com", "SuperSecret123", UserRole.STUDENT)
    assert user.password_hash != "SuperSecret123"
    assert "SuperSecret123" not in user.password_hash
