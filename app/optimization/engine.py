"""Optimization engine: OR-Tools CP-SAT based hostel/bed assignment.

Decision variable x[s,b] in {0,1}: student s is assigned to bed b.

Hard constraints:
  1. Sum over b of x[s,b] <= 1           (at most one bed per student)
  2. Sum over s of x[s,b] <= 1           (at most one student per bed)
  3. Only eligible/verified applicants and usable beds generate variables
  4. Gender/category compatibility enforced at candidate-generation time
  5. Academic session is fixed per run

Objective: maximize sum of assignment scores (priority + preference +
room-type contribution - penalties), sourced from the HOS-004 scoring
service so scoring logic is never duplicated here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ortools.sat.python import cp_model
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import OptimizationError
from app.core.logging_config import get_logger
from app.models.application import (
    Application, ApplicationStatus, EligibilityStatus, HostelPreference,
)
from app.models.hostel import AccommodationStatus, BedSpace, BedStatus, Hostel, HostelCategory, Room
from app.models.optimization import OptimizationRun, OptimizationStatus, UnallocatedReason, UnallocatedRecord
from app.models.student import Gender, Student
from app.services.priority_service import calculate_assignment_score, calculate_priority_score, active_penalties

logger = get_logger("optimization.engine")


@dataclass
class Candidate:
    student_id: int
    application_id: int
    bed_id: int
    room_id: int
    hostel_id: int
    block_id: int
    floor_id: int
    score: float
    preference_rank: int | None
    reason_parts: list[str] = field(default_factory=list)


@dataclass
class OptimizationOutcome:
    run_id: int
    status: OptimizationStatus
    applicant_count: int
    bed_space_count: int
    allocated_count: int
    unallocated_count: int
    objective_score: float | None
    execution_time: float
    assignments: list[Candidate]
    unallocated_student_ids: list[int]


def _gender_compatible(student_gender: Gender, hostel_category: HostelCategory) -> bool:
    if hostel_category == HostelCategory.MIXED:
        return True
    return hostel_category.value == student_gender.value


def _eligible_applications(session: Session, academic_session: str) -> list[Application]:
    stmt = (
        select(Application)
        .where(
            Application.academic_session == academic_session,
            Application.status == ApplicationStatus.VERIFIED,
            Application.eligibility_status == EligibilityStatus.ELIGIBLE,
        )
    )
    return list(session.scalars(stmt).all())


def _usable_beds(session: Session) -> list[BedSpace]:
    stmt = (
        select(BedSpace)
        .join(Room, BedSpace.room_id == Room.id)
        .where(BedSpace.status == BedStatus.AVAILABLE, Room.status == AccommodationStatus.ACTIVE)
    )
    beds = list(session.scalars(stmt).all())
    usable = []
    for bed in beds:
        room = bed.room
        floor = room.floor
        block = floor.block
        hostel = block.hostel
        if (
            room.status == AccommodationStatus.ACTIVE
            and floor.status == AccommodationStatus.ACTIVE
            and block.status == AccommodationStatus.ACTIVE
            and hostel.status == AccommodationStatus.ACTIVE
        ):
            usable.append(bed)
    return usable


def generate_candidates(session: Session, applications: list[Application], beds: list[BedSpace]) -> list[Candidate]:
    """Pre-filter to valid (student, bed) pairs and compute assignment scores.
    This keeps the solver's search space to genuinely possible assignments.
    """
    penalties = active_penalties(session)
    candidates: list[Candidate] = []

    beds_by_hostel: dict[int, list[BedSpace]] = {}
    for bed in beds:
        hostel_id = bed.room.floor.block.hostel_id
        beds_by_hostel.setdefault(hostel_id, []).append(bed)

    for application in applications:
        student = application.student
        priority = calculate_priority_score(session, application.id)

        prefs = {p.hostel_id: p.preference_rank for p in application.preferences}
        # Preferred hostels first; if none compatible, fall back to any compatible hostel.
        candidate_hostel_ids = list(prefs.keys()) or list(beds_by_hostel.keys())

        added_for_student = 0
        for hostel_id in candidate_hostel_ids:
            hostel = session.get(Hostel, hostel_id)
            if not hostel or not _gender_compatible(student.gender, hostel.category):
                continue
            for bed in beds_by_hostel.get(hostel_id, []):
                room = bed.room
                room_match = None
                if application.preferred_room_type:
                    room_match = room.room_type.value == application.preferred_room_type
                result = calculate_assignment_score(
                    session,
                    priority_total=priority.total_score,
                    preference_rank=prefs.get(hostel_id),
                    room_type_match=room_match,
                    penalties=penalties,
                )
                reason_parts = []
                if prefs.get(hostel_id) == 1:
                    reason_parts.append("1st hostel preference")
                elif hostel_id in prefs:
                    reason_parts.append(f"preference rank {prefs[hostel_id]}")
                if room_match:
                    reason_parts.append("compatible room type")
                if priority.total_score > 0:
                    reason_parts.append("priority score contribution")

                candidates.append(Candidate(
                    student_id=student.id, application_id=application.id, bed_id=bed.id,
                    room_id=room.id, hostel_id=hostel_id, block_id=room.floor.block_id,
                    floor_id=room.floor_id, score=result.total_score,
                    preference_rank=prefs.get(hostel_id), reason_parts=reason_parts,
                ))
                added_for_student += 1

        # Fallback: if the student had no compatible candidates yet (e.g. all
        # preferred hostels incompatible/full), consider ANY compatible hostel.
        if added_for_student == 0:
            for hostel_id, hbeds in beds_by_hostel.items():
                hostel = session.get(Hostel, hostel_id)
                if not hostel or not _gender_compatible(student.gender, hostel.category):
                    continue
                for bed in hbeds:
                    result = calculate_assignment_score(
                        session, priority_total=priority.total_score,
                        preference_rank=None, room_type_match=None, penalties=penalties,
                    )
                    candidates.append(Candidate(
                        student_id=student.id, application_id=application.id, bed_id=bed.id,
                        room_id=bed.room_id, hostel_id=hostel_id, block_id=bed.room.floor.block_id,
                        floor_id=bed.room.floor_id, score=result.total_score,
                        preference_rank=None, reason_parts=["no preferred hostel available; priority-based"],
                    ))
    return candidates


def run_optimization(session: Session, *, academic_session: str, time_limit_seconds: int = 60,
                      created_by: int | None = None) -> OptimizationOutcome:
    start = time.monotonic()

    # Prevent concurrent conflicting runs for the same session.
    active = session.scalars(
        select(OptimizationRun).where(
            OptimizationRun.academic_session == academic_session,
            OptimizationRun.status == OptimizationStatus.RUNNING,
        )
    ).first()
    if active:
        raise OptimizationError(f"An optimization run is already in progress for {academic_session}.")

    run = OptimizationRun(
        academic_session=academic_session, status=OptimizationStatus.RUNNING,
        started_at=datetime.now(timezone.utc), solver_time_limit_seconds=time_limit_seconds,
        rule_set_version="v1", created_by=created_by,
    )
    session.add(run)
    session.flush()

    try:
        applications = _eligible_applications(session, academic_session)
        beds = _usable_beds(session)
        run.applicant_count = len(applications)
        run.bed_space_count = len(beds)

        if not applications:
            run.status = OptimizationStatus.INFEASIBLE
            run.error_message = "No eligible, verified applicants found for this session."
            run.completed_at = datetime.now(timezone.utc)
            run.execution_time = time.monotonic() - start
            session.flush()
            return OptimizationOutcome(run.id, run.status, 0, len(beds), 0, 0, None,
                                        run.execution_time, [], [])

        candidates = generate_candidates(session, applications, beds)

        if not candidates or not beds:
            # No feasible assignments at all — everyone is unallocated, but this is
            # still a valid (empty) result, not a crash.
            for app_ in applications:
                session.add(UnallocatedRecord(
                    optimization_run_id=run.id, student_id=app_.student_id, application_id=app_.id,
                    reason=UnallocatedReason.NO_COMPATIBLE_HOSTEL if beds else UnallocatedReason.NO_AVAILABLE_BED,
                ))
            run.status = OptimizationStatus.FEASIBLE
            run.allocated_count = 0
            run.unallocated_count = len(applications)
            run.objective_score = 0
            run.completed_at = datetime.now(timezone.utc)
            run.execution_time = time.monotonic() - start
            session.flush()
            return OptimizationOutcome(run.id, run.status, len(applications), len(beds), 0,
                                        len(applications), 0, run.execution_time, [],
                                        [a.student_id for a in applications])

        model = cp_model.CpModel()
        x_vars = {}
        for idx, c in enumerate(candidates):
            x_vars[idx] = model.NewBoolVar(f"x_{c.student_id}_{c.bed_id}")

        by_student: dict[int, list[int]] = {}
        by_bed: dict[int, list[int]] = {}
        for idx, c in enumerate(candidates):
            by_student.setdefault(c.student_id, []).append(idx)
            by_bed.setdefault(c.bed_id, []).append(idx)

        # Constraint 1: at most one bed per student
        for student_id, idxs in by_student.items():
            model.Add(sum(x_vars[i] for i in idxs) <= 1)

        # Constraint 2: at most one student per bed
        for bed_id, idxs in by_bed.items():
            model.Add(sum(x_vars[i] for i in idxs) <= 1)

        # Objective: maximize total assignment score (scaled to integers for CP-SAT)
        objective_terms = []
        for idx, c in enumerate(candidates):
            scaled_score = int(round(c.score * 100))
            objective_terms.append(scaled_score * x_vars[idx])
        model.Maximize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit_seconds)
        solver.parameters.num_search_workers = 8

        status_code = solver.Solve(model)

        status_map = {
            cp_model.OPTIMAL: OptimizationStatus.OPTIMAL,
            cp_model.FEASIBLE: OptimizationStatus.FEASIBLE,
            cp_model.INFEASIBLE: OptimizationStatus.INFEASIBLE,
            cp_model.UNKNOWN: OptimizationStatus.UNKNOWN,
        }
        # If a time limit is hit before optimality is proven but a feasible
        # solution exists, report it accurately as TIME_LIMIT / FEASIBLE.
        if status_code == cp_model.FEASIBLE and solver.WallTime() >= time_limit_seconds - 0.5:
            run.status = OptimizationStatus.TIME_LIMIT
        else:
            run.status = status_map.get(status_code, OptimizationStatus.UNKNOWN)

        assignments: list[Candidate] = []
        allocated_student_ids: set[int] = set()

        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for idx, c in enumerate(candidates):
                if solver.Value(x_vars[idx]) == 1:
                    assignments.append(c)
                    allocated_student_ids.add(c.student_id)
            run.objective_score = solver.ObjectiveValue() / 100.0
        else:
            run.objective_score = None

        all_student_ids = {app_.student_id for app_ in applications}
        unallocated_ids = all_student_ids - allocated_student_ids

        candidate_students = {c.student_id for c in candidates}
        for app_ in applications:
            if app_.student_id in unallocated_ids:
                if app_.student_id not in candidate_students:
                    reason = UnallocatedReason.NO_COMPATIBLE_HOSTEL
                elif len(beds) < len(applications):
                    reason = UnallocatedReason.CAPACITY_EXHAUSTED
                else:
                    reason = UnallocatedReason.NO_VALID_ASSIGNMENT
                session.add(UnallocatedRecord(
                    optimization_run_id=run.id, student_id=app_.student_id,
                    application_id=app_.id, reason=reason,
                ))

        run.allocated_count = len(assignments)
        run.unallocated_count = len(unallocated_ids)
        run.completed_at = datetime.now(timezone.utc)
        run.execution_time = time.monotonic() - start
        session.flush()

        return OptimizationOutcome(
            run_id=run.id, status=run.status, applicant_count=len(applications),
            bed_space_count=len(beds), allocated_count=len(assignments),
            unallocated_count=len(unallocated_ids), objective_score=run.objective_score,
            execution_time=run.execution_time, assignments=assignments,
            unallocated_student_ids=list(unallocated_ids),
        )

    except Exception as exc:  # noqa: BLE001
        run.status = OptimizationStatus.FAILED
        run.error_message = str(exc)[:500]
        run.completed_at = datetime.now(timezone.utc)
        run.execution_time = time.monotonic() - start
        session.flush()
        logger.exception("Optimization run %s failed", run.id)
        raise OptimizationError("The optimization run failed. See the run record for details.") from exc
