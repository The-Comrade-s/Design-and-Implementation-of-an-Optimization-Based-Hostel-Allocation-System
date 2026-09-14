from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from app.models.allocation import AllocationHistory, AllocationResult, AllocationStatus
from app.models.hostel import AccommodationStatus, BedSpace, BedStatus
from app.models.notification import Notification
from app.services.audit_service import log_action

ACTIVE_STATUSES = (
    AllocationStatus.PROPOSED, AllocationStatus.UNDER_REVIEW,
    AllocationStatus.APPROVED, AllocationStatus.PUBLISHED,
)


def _snapshot(allocation: AllocationResult) -> str:
    return json.dumps({
        "hostel_id": allocation.hostel_id, "room_id": allocation.room_id,
        "bed_space_id": allocation.bed_space_id, "status": allocation.status.value,
    })


def _record_history(session: Session, allocation: AllocationResult, actor_id: int | None,
                     change_type: str, previous_state: str, reason: str | None) -> None:
    session.add(AllocationHistory(
        allocation_id=allocation.id, changed_by=actor_id, change_type=change_type,
        previous_state=previous_state, new_state=_snapshot(allocation), reason=reason,
    ))


def list_proposed_allocations(session: Session, optimization_run_id: int) -> list[AllocationResult]:
    stmt = select(AllocationResult).where(AllocationResult.optimization_run_id == optimization_run_id)
    return list(session.scalars(stmt).all())


def override_allocation(session: Session, allocation_id: int, *, new_bed_id: int, reason: str,
                         actor_id: int) -> AllocationResult:
    if not reason or not reason.strip():
        raise ValidationError("An override reason is required.")

    allocation = session.get(AllocationResult, allocation_id)
    if not allocation:
        raise NotFoundError("Allocation not found.")
    if allocation.status not in (AllocationStatus.PROPOSED, AllocationStatus.UNDER_REVIEW):
        raise BusinessRuleError("Only proposed/under-review allocations can be overridden.")

    new_bed = session.get(BedSpace, new_bed_id)
    if not new_bed or new_bed.status != BedStatus.AVAILABLE:
        raise ValidationError("Selected bed is not available.")
    room = new_bed.room
    if room.status != AccommodationStatus.ACTIVE:
        raise ValidationError("Selected room is not active.")

    # Bed must not already be actively allocated to someone else this session.
    conflict = session.scalars(
        select(AllocationResult).where(
            AllocationResult.bed_space_id == new_bed_id,
            AllocationResult.academic_session == allocation.academic_session,
            AllocationResult.status.in_(ACTIVE_STATUSES),
            AllocationResult.id != allocation.id,
        )
    ).first()
    if conflict:
        raise BusinessRuleError("The selected bed is already allocated for this session.")

    # Gender compatibility must still hold.
    student = allocation.student
    hostel = room.floor.block.hostel
    if hostel.category.value not in ("MIXED", student.gender.value):
        raise BusinessRuleError("Override violates gender/category compatibility rules.")

    previous = _snapshot(allocation)
    allocation.hostel_id = hostel.id
    allocation.block_id = room.floor.block_id
    allocation.floor_id = room.floor_id
    allocation.room_id = room.id
    allocation.bed_space_id = new_bed.id
    allocation.status = AllocationStatus.UNDER_REVIEW
    session.flush()
    _record_history(session, allocation, actor_id, "OVERRIDE", previous, reason)
    log_action(session, user_id=actor_id, action="ALLOCATION_MODIFIED",
               entity_type="AllocationResult", entity_id=allocation.id, description=reason)
    return allocation


def approve_allocation(session: Session, allocation_id: int, actor_id: int) -> AllocationResult:
    allocation = session.get(AllocationResult, allocation_id)
    if not allocation:
        raise NotFoundError("Allocation not found.")
    if allocation.status not in (AllocationStatus.PROPOSED, AllocationStatus.UNDER_REVIEW):
        raise BusinessRuleError("Only proposed/under-review allocations can be approved.")
    previous = _snapshot(allocation)
    allocation.status = AllocationStatus.APPROVED
    allocation.approved_by = actor_id
    allocation.approved_at = datetime.now(timezone.utc)
    session.flush()
    _record_history(session, allocation, actor_id, "APPROVE", previous, None)
    log_action(session, user_id=actor_id, action="ALLOCATION_APPROVED",
               entity_type="AllocationResult", entity_id=allocation.id)
    return allocation


def bulk_approve(session: Session, allocation_ids: list[int], actor_id: int) -> tuple[list[int], list[str]]:
    succeeded, errors = [], []
    for aid in allocation_ids:
        try:
            approve_allocation(session, aid, actor_id)
            succeeded.append(aid)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Allocation {aid}: {exc}")
    return succeeded, errors


def publish_allocation(session: Session, allocation_id: int, actor_id: int) -> AllocationResult:
    allocation = session.get(AllocationResult, allocation_id)
    if not allocation:
        raise NotFoundError("Allocation not found.")
    if allocation.status != AllocationStatus.APPROVED:
        raise BusinessRuleError("Only approved allocations can be published.")

    # Enforce one active published allocation per student/session.
    conflict = session.scalars(
        select(AllocationResult).where(
            AllocationResult.student_id == allocation.student_id,
            AllocationResult.academic_session == allocation.academic_session,
            AllocationResult.status == AllocationStatus.PUBLISHED,
            AllocationResult.id != allocation.id,
        )
    ).first()
    if conflict:
        raise BusinessRuleError("Student already has a published allocation for this session.")

    previous = _snapshot(allocation)
    allocation.status = AllocationStatus.PUBLISHED
    allocation.published_at = datetime.now(timezone.utc)
    # Bed is now consumed; downstream availability queries treat active
    # AllocationResult rows as authoritative occupancy, so bed status stays
    # AVAILABLE at the infrastructure level but is excluded via allocation join.
    session.flush()
    _record_history(session, allocation, actor_id, "PUBLISH", previous, None)
    log_action(session, user_id=actor_id, action="ALLOCATION_PUBLISHED",
               entity_type="AllocationResult", entity_id=allocation.id)

    session.add(Notification(
        user_id=allocation.student.user_id,
        title="Hostel allocation published",
        message=(f"Your hostel allocation for {allocation.academic_session} has been published. "
                 "View your allocation for full details."),
        link="my_allocation",
    ))
    session.flush()
    return allocation


def bulk_publish(session: Session, allocation_ids: list[int], actor_id: int) -> tuple[list[int], list[str]]:
    succeeded, errors = [], []
    for aid in allocation_ids:
        try:
            publish_allocation(session, aid, actor_id)
            succeeded.append(aid)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Allocation {aid}: {exc}")
    return succeeded, errors


def release_allocation(session: Session, allocation_id: int, reason: str, actor_id: int) -> AllocationResult:
    if not reason or not reason.strip():
        raise ValidationError("A release reason is required.")
    allocation = session.get(AllocationResult, allocation_id)
    if not allocation:
        raise NotFoundError("Allocation not found.")
    if allocation.status not in (AllocationStatus.PUBLISHED, AllocationStatus.APPROVED):
        raise BusinessRuleError("Only an approved/published allocation can be released.")

    previous = _snapshot(allocation)
    allocation.status = AllocationStatus.RELEASED
    allocation.released_at = datetime.now(timezone.utc)
    allocation.release_reason = reason
    session.flush()
    _record_history(session, allocation, actor_id, "RELEASE", previous, reason)
    log_action(session, user_id=actor_id, action="ALLOCATION_RELEASED",
               entity_type="AllocationResult", entity_id=allocation.id, description=reason)
    return allocation


def get_published_allocation_for_student(session: Session, student_id: int, academic_session: str) -> AllocationResult | None:
    return session.scalars(
        select(AllocationResult).where(
            AllocationResult.student_id == student_id,
            AllocationResult.academic_session == academic_session,
            AllocationResult.status == AllocationStatus.PUBLISHED,
        )
    ).first()


def occupied_bed_ids(session: Session, academic_session: str) -> set[int]:
    stmt = select(AllocationResult.bed_space_id).where(
        AllocationResult.academic_session == academic_session,
        AllocationResult.status.in_(ACTIVE_STATUSES),
    )
    return set(session.scalars(stmt).all())
