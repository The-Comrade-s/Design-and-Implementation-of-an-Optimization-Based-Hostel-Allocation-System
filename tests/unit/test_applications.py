from __future__ import annotations

import pytest

from app.core.exceptions import BusinessRuleError, ConflictError, ValidationError
from app.models.hostel import HostelCategory
from app.models.student import Gender
from app.models.user import UserRole
from app.services import application_service, hostel_service, student_service
from app.services.auth_service import register_user


def _setup(session):
    user = register_user(session, "stu@x.com", "Password123", UserRole.STUDENT)
    student = student_service.create_student(
        session, user_id=user.id, student_id="STU001", first_name="A", last_name="B",
        gender=Gender.FEMALE, email="stu@x.com", department="CS", programme="CS",
        level="400", academic_session="2026/2027",
    )
    hostel = hostel_service.create_hostel(session, name="Hostel A", code="H-A", category=HostelCategory.MIXED)
    return student, hostel


def test_create_application_and_duplicate_rejected(session):
    student, _ = _setup(session)
    application_service.create_application(session, student_id=student.id, academic_session="2026/2027")
    with pytest.raises(ConflictError):
        application_service.create_application(session, student_id=student.id, academic_session="2026/2027")


def test_submit_requires_preferences(session):
    student, hostel = _setup(session)
    app_ = application_service.create_application(session, student_id=student.id, academic_session="2026/2027")
    with pytest.raises(ValidationError):
        application_service.submit_application(session, app_.id)


def test_duplicate_hostel_preference_rejected(session):
    student, hostel = _setup(session)
    app_ = application_service.create_application(session, student_id=student.id, academic_session="2026/2027")
    with pytest.raises(ValidationError):
        application_service.set_hostel_preferences(session, app_.id, [(hostel.id, 1), (hostel.id, 2)])


def test_submit_and_verify_workflow(session):
    student, hostel = _setup(session)
    app_ = application_service.create_application(session, student_id=student.id, academic_session="2026/2027")
    application_service.set_hostel_preferences(session, app_.id, [(hostel.id, 1)])
    submitted = application_service.submit_application(session, app_.id)
    assert submitted.status.value == "SUBMITTED"

    verified = application_service.verify_application(session, app_.id, verifier_user_id=1)
    assert verified.status.value == "VERIFIED"


def test_cannot_verify_ineligible_application(session):
    from app.models.student import StudentStatus
    student, hostel = _setup(session)
    app_ = application_service.create_application(session, student_id=student.id, academic_session="2026/2027")
    application_service.set_hostel_preferences(session, app_.id, [(hostel.id, 1)])
    application_service.submit_application(session, app_.id)

    student.status = StudentStatus.SUSPENDED
    session.flush()
    app_.eligibility_status = student_service.check_student_eligibility(session, student.id).status
    session.flush()

    with pytest.raises(BusinessRuleError):
        application_service.verify_application(session, app_.id, verifier_user_id=1)
