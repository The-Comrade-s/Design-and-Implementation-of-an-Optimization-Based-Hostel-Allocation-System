from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError
from app.models.student import Gender, StudentStatus
from app.models.user import UserRole
from app.services import student_service
from app.services.auth_service import register_user


def _make_student(session, student_id="STU001", status=StudentStatus.ACTIVE):
    user = register_user(session, f"{student_id.lower()}@x.com", "Password123", UserRole.STUDENT)
    student = student_service.create_student(
        session, user_id=user.id, student_id=student_id, first_name="Amaka", last_name="Obi",
        gender=Gender.FEMALE, email=f"{student_id.lower()}@x.com", department="CS",
        programme="CS", level="400", academic_session="2026/2027",
    )
    student.status = status
    session.flush()
    return student


def test_create_student_and_duplicate_id_rejected(session):
    _make_student(session)
    with pytest.raises(ConflictError):
        _make_student(session)


def test_eligible_active_student(session):
    student = _make_student(session)
    result = student_service.check_student_eligibility(session, student.id)
    assert result.eligible is True
    assert result.status.value == "ELIGIBLE"


def test_ineligible_inactive_student(session):
    student = _make_student(session, status=StudentStatus.SUSPENDED)
    result = student_service.check_student_eligibility(session, student.id)
    assert result.eligible is False
    assert "SUSPENDED" in result.reason
