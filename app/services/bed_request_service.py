"""Student-chosen bed requests.

A student picks a hostel / room / bed space. That choice is stored as an
AllocationResult in PROPOSED state (no optimization run), which reuses the
existing review -> approve -> publish workflow and holds the bed so nobody
else can pick it. The admin then approves (and publishes) it only if the
student qualifies, or declines it with a reason.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from app.models.allocation import AllocationHistory, AllocationResult, AllocationStatus
from app.models.application import ApplicationStatus
from app.models.hostel import AccommodationStatus, BedSpace, BedStatus
from app.models.notification import Notification
from app.models.student import Student
from app.services import allocation_service, application_service
from app.services.allocation_service import ACTIVE_STATUSES
from app.services.audit_service import log_action
from app.services.student_service import check_student_eligibility

PENDING_STATUSES = (AllocationStatus.PROPOSED, AllocationStatus.UNDER_REVIEW)


def get_active_request(session: Session, student_id: int, academic_session: str) -> AllocationResult | None:
    return session.scalars(
        select(AllocationResult).where(
            AllocationResult.student_id == student_id,
            AllocationResult.academic_session == academic_session,
            AllocationResult.status.in_(ACTIVE_STATUSES),
        ).order_by(AllocationResult.id.desc())
    ).first()


def get_last_declined(session: Session, student_id: int, academic_session: str) -> AllocationResult | None:
    return session.scalars(
        select(AllocationResult).where(
            AllocationResult.student_id == student_id,
            AllocationResult.academic_session == academic_session,
            AllocationResult.status == AllocationStatus.CANCELLED,
            AllocationResult.release_reason.is_not(None),
        ).order_by(AllocationResult.id.desc())
    ).first()


def create_bed_request(session: Session, *, student_id: int, bed_id: int,
                       actor_id: int | None = None) -> AllocationResult:
    student = session.get(Student, student_id)
    if not student:
        raise NotFoundError("Student not found.")

    eligibility = check_student_eligibility(session, student_id)
    if not eligibility.eligible:
        raise BusinessRuleError(f"You cannot request a bed yet: {eligibility.reason}")

    if get_active_request(session, student_id, student.academic_session):
        raise BusinessRuleError(
            "You already have an active bed request or allocation. Cancel the request first to choose another bed."
        )

    bed = session.get(BedSpace, bed_id)
    if not bed or bed.status != BedStatus.AVAILABLE:
        raise ValidationError("That bed space is not available.")
    room = bed.room
    floor = room.floor
    block = floor.block
    hostel = block.hostel
    if any(x.status != AccommodationStatus.ACTIVE for x in (room, floor, block, hostel)):
        raise ValidationError("That bed space is not in an active room/hostel.")
    if hostel.category.value not in ("MIXED", student.gender.value):
        raise BusinessRuleError("This hostel is not open to your gender category.")

    taken = session.scalars(
        select(AllocationResult).where(
            AllocationResult.bed_space_id == bed_id,
            AllocationResult.academic_session == student.academic_session,
            AllocationResult.status.in_(ACTIVE_STATUSES),
        )
    ).first()
    if taken:
        raise ConflictError("Sorry, that bed was just taken by another student. Please choose another.")

    application = application_service.get_student_application(session, student_id, student.academic_session)
    if application is None:
        application = application_service.create_application(
            session, student_id=student_id, academic_session=student.academic_session, actor_id=actor_id,
        )
    if application.status in (ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN):
        raise BusinessRuleError("Your application was rejected or withdrawn. Please contact the hostel administrator.")
    if application.status == ApplicationStatus.DRAFT:
        application_service.set_hostel_preferences(session, application.id, [(hostel.id, 1)])
        application_service.submit_application(session, application.id, actor_id)

    allocation = AllocationResult(
        optimization_run_id=None, student_id=student_id, application_id=application.id,
        academic_session=student.academic_session, hostel_id=hostel.id, block_id=block.id,
        floor_id=floor.id, room_id=room.id, bed_space_id=bed.id, allocation_score=0.0,
        preference_rank=None, allocation_reason="Selected by student", status=AllocationStatus.PROPOSED,
    )
    session.add(allocation)
    session.flush()
    log_action(session, user_id=actor_id, action="BED_REQUESTED", entity_type="AllocationResult",
               entity_id=allocation.id, description=f"{hostel.name}/{room.room_number}/{bed.bed_identifier}")
    return allocation


def cancel_bed_request(session: Session, allocation_id: int, student_id: int) -> AllocationResult:
    allocation = session.get(AllocationResult, allocation_id)
    if not allocation or allocation.student_id != student_id:
        raise NotFoundError("Request not found.")
    if allocation.status not in PENDING_STATUSES:
        raise BusinessRuleError("Only a request that is still awaiting review can be cancelled.")
    allocation.status = AllocationStatus.CANCELLED
    allocation.allocation_reason = "Selected by student (cancelled by student)"
    session.flush()
    log_action(session, user_id=allocation.student.user_id, action="BED_REQUEST_CANCELLED",
               entity_type="AllocationResult", entity_id=allocation.id)
    return allocation


def list_requests(session: Session, statuses: tuple[AllocationStatus, ...]) -> list[AllocationResult]:
    return list(session.scalars(
        select(AllocationResult).where(
            AllocationResult.optimization_run_id.is_(None),
            AllocationResult.status.in_(statuses),
        ).order_by(AllocationResult.id.desc())
    ).all())


def approve_request(session: Session, allocation_id: int, actor_id: int) -> AllocationResult:
    """Admin allocates the requested bed (approve + publish) if the student qualifies."""
    allocation = session.get(AllocationResult, allocation_id)
    if not allocation:
        raise NotFoundError("Request not found.")
    if allocation.status not in PENDING_STATUSES + (AllocationStatus.APPROVED,):
        raise BusinessRuleError("This request has already been decided.")

    eligibility = check_student_eligibility(session, allocation.student_id)
    if not eligibility.eligible:
        raise BusinessRuleError(f"Student does not qualify: {eligibility.reason}")

    other = session.scalars(
        select(AllocationResult).where(
            AllocationResult.bed_space_id == allocation.bed_space_id,
            AllocationResult.academic_session == allocation.academic_session,
            AllocationResult.status.in_(ACTIVE_STATUSES),
            AllocationResult.id != allocation.id,
        )
    ).first()
    if other:
        raise BusinessRuleError("That bed is also held by another allocation. Decline this request.")

    application = allocation.application
    if application.status in (ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN):
        raise BusinessRuleError("The student's application was rejected or withdrawn.")
    if application.status in (ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW):
        application.eligibility_status = eligibility.status
        session.flush()
        application_service.verify_application(session, application.id, actor_id)

    if allocation.status in PENDING_STATUSES:
        allocation_service.approve_allocation(session, allocation.id, actor_id)
    allocation_service.publish_allocation(session, allocation.id, actor_id)
    return allocation


def reject_request(session: Session, allocation_id: int, reason: str, actor_id: int) -> AllocationResult:
    if not reason or not reason.strip():
        raise ValidationError("Please give a reason for declining the request.")
    allocation = session.get(AllocationResult, allocation_id)
    if not allocation:
        raise NotFoundError("Request not found.")
    if allocation.status not in PENDING_STATUSES:
        raise BusinessRuleError("Only a pending request can be declined.")

    previous = allocation_service._snapshot(allocation)
    allocation.status = AllocationStatus.CANCELLED
    allocation.release_reason = reason.strip()
    allocation.released_at = datetime.now(timezone.utc)
    session.flush()
    session.add(AllocationHistory(
        allocation_id=allocation.id, changed_by=actor_id, change_type="REQUEST_DECLINED",
        previous_state=previous, new_state=allocation_service._snapshot(allocation), reason=reason.strip(),
    ))
    session.add(Notification(
        user_id=allocation.student.user_id, title="Bed request declined",
        message=(f"Your request for {allocation.hostel.name} / Room {allocation.room.room_number} / "
                 f"Bed {allocation.bed_space.bed_identifier} was declined: {reason.strip()} "
                 "You can choose another bed."),
        link="choose_bed",
    ))
    session.flush()
    log_action(session, user_id=actor_id, action="BED_REQUEST_DECLINED", entity_type="AllocationResult",
               entity_id=allocation.id, description=reason.strip())
    return allocation
