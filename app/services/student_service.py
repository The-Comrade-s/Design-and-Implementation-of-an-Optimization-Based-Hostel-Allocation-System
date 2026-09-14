from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.application import ApplicationStatus, EligibilityStatus
from app.models.student import Gender, Student, StudentStatus
from app.services.audit_service import log_action


def create_student(session: Session, *, user_id: int, student_id: str, first_name: str, last_name: str,
                    gender: Gender, email: str, department: str, programme: str, level: str,
                    academic_session: str, middle_name: str | None = None, phone_number: str | None = None,
                    faculty: str | None = None, year_of_entry: int | None = None,
                    actor_id: int | None = None) -> Student:
    if not student_id or not first_name or not last_name:
        raise ValidationError("Student ID, first name and last name are required.")
    existing = session.scalars(select(Student).where(Student.student_id == student_id)).first()
    if existing:
        raise ConflictError(f"Student ID '{student_id}' already exists.")

    student = Student(
        user_id=user_id, student_id=student_id, first_name=first_name, middle_name=middle_name,
        last_name=last_name, gender=gender, phone_number=phone_number, email=email,
        faculty=faculty, department=department, programme=programme, level=level,
        academic_session=academic_session, year_of_entry=year_of_entry, status=StudentStatus.ACTIVE,
    )
    session.add(student)
    session.flush()
    log_action(session, user_id=actor_id, action="STUDENT_CREATED", entity_type="Student", entity_id=student.id)
    return student


def get_student_by_user(session: Session, user_id: int) -> Student | None:
    return session.scalars(select(Student).where(Student.user_id == user_id)).first()


def update_student(session: Session, student_id: int, actor_id: int | None = None, **fields) -> Student:
    student = session.get(Student, student_id)
    if not student:
        raise NotFoundError("Student not found.")
    protected = {"student_id"}
    for key, value in fields.items():
        if key in protected:
            continue
        if hasattr(student, key) and value is not None:
            setattr(student, key, value)
    session.flush()
    log_action(session, user_id=actor_id, action="STUDENT_UPDATED", entity_type="Student", entity_id=student.id)
    return student


@dataclass
class EligibilityResult:
    eligible: bool
    status: EligibilityStatus
    reason: str


def check_student_eligibility(session: Session, student_id: int) -> EligibilityResult:
    """Determine accommodation eligibility, independent of the UI.

    Kept intentionally simple/configurable: active status + a valid,
    non-withdrawn academic record is required. Institutions can extend
    this with further configured rules without touching the application
    layer.
    """
    student = session.get(Student, student_id)
    if not student:
        raise NotFoundError("Student not found.")

    if student.status != StudentStatus.ACTIVE:
        return EligibilityResult(
            eligible=False,
            status=EligibilityStatus.NOT_ELIGIBLE,
            reason=f"Student record status is {student.status.value}, not ACTIVE.",
        )

    if not student.department or not student.programme or not student.academic_session:
        return EligibilityResult(
            eligible=False,
            status=EligibilityStatus.PENDING_VERIFICATION,
            reason="Required academic information is incomplete.",
        )

    return EligibilityResult(
        eligible=True,
        status=EligibilityStatus.ELIGIBLE,
        reason="Student is active and meets current accommodation requirements.",
    )
