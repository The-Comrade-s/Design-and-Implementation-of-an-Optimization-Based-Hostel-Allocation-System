from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.application import Application, RequirementVerificationStatus
from app.models.priority import (
    PenaltyConfig, PreferenceScoreConfig, PriorityCriterion, PriorityScoreDetail, StudentPriorityScore,
)
from app.models.student import Student

CALCULATION_VERSION = "v1"


@dataclass
class ScoreBreakdownItem:
    code: str
    raw_value: float
    weighted_score: float
    explanation: str


@dataclass
class AssignmentScoreResult:
    total_score: float
    priority_score: float
    preference_score: float
    room_preference_score: float
    penalty: float
    breakdown: list[ScoreBreakdownItem] = field(default_factory=list)


def _final_year_raw(student: Student) -> float:
    return 1.0 if str(student.level).strip() in {"400", "500", "600", "FINAL", "FINAL_YEAR"} else 0.0


def calculate_priority_score(session: Session, application_id: int) -> StudentPriorityScore:
    """Calculate (and persist) a student's configurable, weighted priority score."""
    application = session.get(Application, application_id)
    if not application:
        raise NotFoundError("Application not found.")
    student = session.get(Student, application.student_id)
    if not student:
        raise NotFoundError("Student not found.")

    criteria = list(session.scalars(select(PriorityCriterion).where(PriorityCriterion.is_active.is_(True))).all())

    existing = session.scalars(
        select(StudentPriorityScore).where(StudentPriorityScore.application_id == application_id)
    ).first()
    if existing:
        for d in list(existing.details):
            session.delete(d)
        session.flush()
    else:
        existing = StudentPriorityScore(
            student_id=student.id, application_id=application.id,
            total_score=0.0, calculation_version=CALCULATION_VERSION,
            calculated_at=datetime.now(timezone.utc),
        )
        session.add(existing)
        session.flush()

    total = 0.0
    for criterion in criteria:
        raw, explanation = _evaluate_criterion(criterion.code, student, application)
        weighted = raw * criterion.weight
        weighted = min(weighted, criterion.maximum_score)
        total += weighted
        session.add(PriorityScoreDetail(
            priority_score_id=existing.id, criterion_id=criterion.id,
            raw_value=raw, weighted_score=weighted, explanation=explanation,
        ))

    existing.total_score = total
    existing.calculation_version = CALCULATION_VERSION
    existing.calculated_at = datetime.now(timezone.utc)
    existing.is_complete = True
    session.flush()
    session.expire(existing, ["details"])
    return existing


def _evaluate_criterion(code: str, student: Student, application: Application) -> tuple[float, str]:
    if code == "FINAL_YEAR":
        raw = _final_year_raw(student)
        return raw, "Applicant is in final year." if raw else "Applicant is not in final year."
    if code == "SPECIAL_REQUIREMENT":
        raw = 1.0 if application.special_requirement_status == RequirementVerificationStatus.VERIFIED else 0.0
        return raw, "Verified special accommodation requirement." if raw else "No verified requirement."
    if code == "RETURNING_STUDENT":
        raw = 1.0 if (student.year_of_entry or 0) < int(student.academic_session.split("/")[0]) else 0.0
        return raw, "Returning student." if raw else "Not a returning student (or new intake)."
    if code == "ACADEMIC_LEVEL":
        try:
            level_num = int(str(student.level).strip())
            raw = min(level_num / 500.0, 1.0)
        except ValueError:
            raw = 0.0
        return raw, f"Academic level {student.level}."
    if code == "DISTANCE":
        # No verified distance data captured yet; do not invent a value.
        return 0.0, "Distance information has not been verified."
    return 0.0, "No applicable data for this criterion."


def preference_rank_score(session: Session, preference_rank: int | None) -> float:
    if preference_rank is None:
        return 0.0
    config = session.scalars(
        select(PreferenceScoreConfig).where(
            PreferenceScoreConfig.preference_rank == preference_rank,
            PreferenceScoreConfig.is_active.is_(True),
        )
    ).first()
    return config.score if config else 0.0


def active_penalties(session: Session) -> dict[str, float]:
    penalties = session.scalars(select(PenaltyConfig).where(PenaltyConfig.is_active.is_(True))).all()
    return {p.code: p.penalty_value for p in penalties}


def calculate_assignment_score(
    session: Session, *, priority_total: float, preference_rank: int | None,
    room_type_match: bool | None, penalties: dict[str, float] | None = None,
) -> AssignmentScoreResult:
    """Combine priority + preference + room-type + penalty into a single
    explainable assignment score, consumed by the optimization engine."""
    penalties = penalties if penalties is not None else active_penalties(session)

    pref_score = preference_rank_score(session, preference_rank)

    room_score = 0.0
    penalty_total = 0.0
    if room_type_match is True:
        room_score = 10.0
    elif room_type_match is False:
        penalty_total += penalties.get("ROOM_TYPE_MISMATCH", 0.0)

    total = priority_total + pref_score + room_score - penalty_total

    breakdown = [
        ScoreBreakdownItem("PRIORITY", priority_total, priority_total, "Weighted priority score."),
        ScoreBreakdownItem("PREFERENCE", preference_rank or 0, pref_score, f"Preference rank {preference_rank}."),
        ScoreBreakdownItem("ROOM_TYPE", 1 if room_type_match else 0, room_score - penalty_total,
                            "Room-type preference contribution/penalty."),
    ]

    return AssignmentScoreResult(
        total_score=total, priority_score=priority_total, preference_score=pref_score,
        room_preference_score=room_score, penalty=penalty_total, breakdown=breakdown,
    )


def seed_default_rules(session: Session) -> None:
    """Idempotently seed sensible default, fully configurable scoring rules."""
    defaults_criteria = [
        ("Final Year Student", "FINAL_YEAR", 30.0, 30.0),
        ("Verified Special Requirement", "SPECIAL_REQUIREMENT", 25.0, 25.0),
        ("Distance", "DISTANCE", 20.0, 20.0),
        ("Academic Level", "ACADEMIC_LEVEL", 15.0, 15.0),
        ("Returning Student", "RETURNING_STUDENT", 10.0, 10.0),
    ]
    for name, code, weight, max_score in defaults_criteria:
        existing = session.scalars(select(PriorityCriterion).where(PriorityCriterion.code == code)).first()
        if not existing:
            session.add(PriorityCriterion(name=name, code=code, weight=weight, maximum_score=max_score, is_active=True))

    defaults_prefs = [(1, 100.0), (2, 70.0), (3, 40.0)]
    for rank, score in defaults_prefs:
        existing = session.scalars(
            select(PreferenceScoreConfig).where(PreferenceScoreConfig.preference_rank == rank)
        ).first()
        if not existing:
            session.add(PreferenceScoreConfig(preference_rank=rank, score=score, is_active=True))

    existing_penalty = session.scalars(
        select(PenaltyConfig).where(PenaltyConfig.code == "ROOM_TYPE_MISMATCH")
    ).first()
    if not existing_penalty:
        session.add(PenaltyConfig(code="ROOM_TYPE_MISMATCH", description="Room type does not match preference",
                                   penalty_value=5.0, is_active=True))
    session.flush()
