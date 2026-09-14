from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.allocation import AllocationResult, AllocationStatus
from app.models.application import Application, ApplicationStatus, EligibilityStatus
from app.models.hostel import BedSpace, BedStatus
from app.models.optimization import OptimizationRun, UnallocatedRecord
from app.models.student import Student
from app.services.hostel_service import hostel_capacity_overview, total_bed_count, usable_bed_count

ACTIVE_ALLOC_STATUSES = (
    AllocationStatus.PROPOSED, AllocationStatus.UNDER_REVIEW,
    AllocationStatus.APPROVED, AllocationStatus.PUBLISHED,
)


def admin_kpis(session: Session, academic_session: str | None = None) -> dict:
    total_students = session.scalar(select(func.count()).select_from(Student)) or 0

    app_stmt = select(func.count()).select_from(Application)
    if academic_session:
        app_stmt = app_stmt.where(Application.academic_session == academic_session)
    total_applications = session.scalar(app_stmt) or 0

    elig_stmt = select(func.count()).select_from(Application).where(
        Application.eligibility_status == EligibilityStatus.ELIGIBLE
    )
    if academic_session:
        elig_stmt = elig_stmt.where(Application.academic_session == academic_session)
    eligible_applicants = session.scalar(elig_stmt) or 0

    total_beds = total_bed_count(session)
    usable_beds = usable_bed_count(session)

    alloc_stmt = select(func.count()).select_from(AllocationResult).where(
        AllocationResult.status == AllocationStatus.PUBLISHED
    )
    if academic_session:
        alloc_stmt = alloc_stmt.where(AllocationResult.academic_session == academic_session)
    allocated = session.scalar(alloc_stmt) or 0

    unallocated = max(eligible_applicants - allocated, 0)
    occupancy_rate = round((allocated / usable_beds) * 100, 2) if usable_beds else 0.0
    allocation_rate = round((allocated / eligible_applicants) * 100, 2) if eligible_applicants else 0.0

    return {
        "total_students": total_students,
        "total_applications": total_applications,
        "eligible_applicants": eligible_applicants,
        "total_bed_spaces": total_beds,
        "usable_bed_spaces": usable_beds,
        "allocated": allocated,
        "unallocated": unallocated,
        "occupancy_rate": occupancy_rate,
        "allocation_rate": allocation_rate,
    }


def hostel_occupancy_report(session: Session) -> list[dict]:
    return hostel_capacity_overview(session)


def application_status_breakdown(session: Session, academic_session: str | None = None) -> dict:
    stmt = select(Application.status, func.count()).group_by(Application.status)
    if academic_session:
        stmt = stmt.where(Application.academic_session == academic_session)
    return {status.value: count for status, count in session.execute(stmt).all()}


def preference_satisfaction(session: Session, academic_session: str) -> dict:
    stmt = select(AllocationResult.preference_rank, func.count()).where(
        AllocationResult.academic_session == academic_session,
        AllocationResult.status.in_(ACTIVE_ALLOC_STATUSES),
    ).group_by(AllocationResult.preference_rank)
    rows = session.execute(stmt).all()
    total = sum(c for _, c in rows) or 1
    result = {"first_choice": 0, "second_choice": 0, "third_choice": 0, "other": 0}
    for rank, count in rows:
        if rank == 1:
            result["first_choice"] += count
        elif rank == 2:
            result["second_choice"] += count
        elif rank == 3:
            result["third_choice"] += count
        else:
            result["other"] += count
    return {k: round((v / total) * 100, 2) for k, v in result.items()} | {"_total": total - 1 + 1}


def unallocated_reasons_breakdown(session: Session, optimization_run_id: int | None = None) -> dict:
    stmt = select(UnallocatedRecord.reason, func.count()).group_by(UnallocatedRecord.reason)
    if optimization_run_id:
        stmt = stmt.where(UnallocatedRecord.optimization_run_id == optimization_run_id)
    return {reason.value: count for reason, count in session.execute(stmt).all()}


def optimization_run_history(session: Session, academic_session: str | None = None) -> list[OptimizationRun]:
    stmt = select(OptimizationRun).order_by(OptimizationRun.created_at.desc())
    if academic_session:
        stmt = stmt.where(OptimizationRun.academic_session == academic_session)
    return list(session.scalars(stmt).all())
