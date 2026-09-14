from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from app.models.application import Application, ApplicationStatus, EligibilityStatus, HostelPreference
from app.models.hostel import AccommodationStatus, Hostel
from app.services.audit_service import log_action
from app.services.student_service import check_student_eligibility


def _next_reference_sequence(session: Session, academic_session: str) -> int:
    year = academic_session.split("/")[0] if "/" in academic_session else academic_session
    count = session.scalar(
        select(func.count()).select_from(Application).where(Application.academic_session == academic_session)
    ) or 0
    return count + 1


def create_application(session: Session, *, student_id: int, academic_session: str,
                        actor_id: int | None = None) -> Application:
    existing = session.scalars(
        select(Application).where(
            Application.student_id == student_id,
            Application.academic_session == academic_session,
        )
    ).first()
    if existing:
        raise ConflictError("Student already has an application for this academic session.")

    eligibility = check_student_eligibility(session, student_id)

    seq = _next_reference_sequence(session, academic_session)
    year = academic_session.split("/")[0] if "/" in academic_session else academic_session
    reference = f"HOS-{year}-{seq:06d}"

    application = Application(
        student_id=student_id,
        academic_session=academic_session,
        application_reference=reference,
        status=ApplicationStatus.DRAFT,
        eligibility_status=eligibility.status,
    )
    session.add(application)
    session.flush()
    log_action(session, user_id=actor_id, action="APPLICATION_CREATED",
               entity_type="Application", entity_id=application.id)
    return application


def set_hostel_preferences(session: Session, application_id: int, hostel_ranks: list[tuple[int, int]]) -> Application:
    """hostel_ranks: list of (hostel_id, preference_rank)."""
    application = session.get(Application, application_id)
    if not application:
        raise NotFoundError("Application not found.")
    if application.status not in (ApplicationStatus.DRAFT,):
        raise BusinessRuleError("Preferences can only be edited while the application is in DRAFT status.")

    hostel_ids = [h for h, _ in hostel_ranks]
    ranks = [r for _, r in hostel_ranks]
    if len(set(hostel_ids)) != len(hostel_ids):
        raise ValidationError("A hostel cannot appear more than once in preferences.")
    if len(set(ranks)) != len(ranks):
        raise ValidationError("Preference ranks must be unique.")
    if any(r <= 0 for r in ranks):
        raise ValidationError("Preference ranks must be positive.")

    for hostel_id in hostel_ids:
        hostel = session.get(Hostel, hostel_id)
        if not hostel or hostel.status != AccommodationStatus.ACTIVE:
            raise ValidationError(f"Hostel {hostel_id} is not available for selection.")

    # Replace existing preferences
    for pref in list(application.preferences):
        session.delete(pref)
    session.flush()

    for hostel_id, rank in hostel_ranks:
        session.add(HostelPreference(application_id=application_id, hostel_id=hostel_id, preference_rank=rank))
    session.flush()
    session.expire(application, ["preferences"])
    return application


def submit_application(session: Session, application_id: int, actor_id: int | None = None) -> Application:
    application = session.get(Application, application_id)
    if not application:
        raise NotFoundError("Application not found.")
    if application.status != ApplicationStatus.DRAFT:
        raise BusinessRuleError("Only a DRAFT application can be submitted.")
    if not application.preferences:
        raise ValidationError("At least one hostel preference is required before submission.")

    eligibility = check_student_eligibility(session, application.student_id)
    application.eligibility_status = eligibility.status

    application.status = ApplicationStatus.SUBMITTED
    application.submitted_at = datetime.now(timezone.utc)
    session.flush()
    log_action(session, user_id=actor_id, action="APPLICATION_SUBMITTED",
               entity_type="Application", entity_id=application.id)
    return application


def verify_application(session: Session, application_id: int, verifier_user_id: int) -> Application:
    application = session.get(Application, application_id)
    if not application:
        raise NotFoundError("Application not found.")
    if application.status not in (ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW):
        raise BusinessRuleError("Only a submitted application under review can be verified.")
    if application.eligibility_status != EligibilityStatus.ELIGIBLE:
        raise BusinessRuleError("Application cannot be verified: student is not eligible.")

    application.status = ApplicationStatus.VERIFIED
    application.verified_at = datetime.now(timezone.utc)
    application.verified_by = verifier_user_id
    session.flush()
    log_action(session, user_id=verifier_user_id, action="APPLICATION_VERIFIED",
               entity_type="Application", entity_id=application.id)
    return application


def reject_application(session: Session, application_id: int, reason: str, actor_id: int) -> Application:
    if not reason or not reason.strip():
        raise ValidationError("A rejection reason is required.")
    application = session.get(Application, application_id)
    if not application:
        raise NotFoundError("Application not found.")
    application.status = ApplicationStatus.REJECTED
    application.rejection_reason = reason
    session.flush()
    log_action(session, user_id=actor_id, action="APPLICATION_REJECTED",
               entity_type="Application", entity_id=application.id, description=reason)
    return application


def get_student_application(session: Session, student_id: int, academic_session: str) -> Application | None:
    return session.scalars(
        select(Application).where(
            Application.student_id == student_id,
            Application.academic_session == academic_session,
        )
    ).first()


def list_applications(session: Session, *, academic_session: str | None = None,
                       status: ApplicationStatus | None = None) -> list[Application]:
    stmt = select(Application)
    if academic_session:
        stmt = stmt.where(Application.academic_session == academic_session)
    if status:
        stmt = stmt.where(Application.status == status)
    return list(session.scalars(stmt.order_by(Application.created_at.desc())).all())
