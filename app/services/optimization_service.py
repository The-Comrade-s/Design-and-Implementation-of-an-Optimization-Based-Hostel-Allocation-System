from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.allocation import AllocationResult, AllocationStatus
from app.optimization.engine import OptimizationOutcome, run_optimization
from app.services.audit_service import log_action


def execute_optimization(session: Session, *, academic_session: str, time_limit_seconds: int = 60,
                          actor_id: int | None = None) -> OptimizationOutcome:
    outcome = run_optimization(
        session, academic_session=academic_session,
        time_limit_seconds=time_limit_seconds, created_by=actor_id,
    )

    for c in outcome.assignments:
        result = AllocationResult(
            optimization_run_id=outcome.run_id, student_id=c.student_id, application_id=c.application_id,
            academic_session=academic_session, hostel_id=c.hostel_id, block_id=c.block_id,
            floor_id=c.floor_id, room_id=c.room_id, bed_space_id=c.bed_id, allocation_score=c.score,
            preference_rank=c.preference_rank,
            allocation_reason="; ".join(c.reason_parts) or "Selected by optimizer based on configured rules.",
            status=AllocationStatus.PROPOSED,
        )
        session.add(result)
    session.flush()

    log_action(
        session, user_id=actor_id, action="OPTIMIZATION_COMPLETED" if outcome.status.value != "FAILED" else "OPTIMIZATION_FAILED",
        entity_type="OptimizationRun", entity_id=outcome.run_id,
        description=f"Allocated={outcome.allocated_count} Unallocated={outcome.unallocated_count} Status={outcome.status.value}",
    )
    return outcome
