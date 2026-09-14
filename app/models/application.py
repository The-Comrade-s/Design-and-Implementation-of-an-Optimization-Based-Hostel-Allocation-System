from __future__ import annotations

import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ApplicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class EligibilityStatus(str, enum.Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class RequirementVerificationStatus(str, enum.Enum):
    NONE = "NONE"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"


class Application(Base, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_session", name="uq_one_application_per_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    academic_session: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    application_reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.DRAFT, nullable=False
    )
    eligibility_status: Mapped[EligibilityStatus] = mapped_column(
        Enum(EligibilityStatus), default=EligibilityStatus.PENDING_VERIFICATION, nullable=False
    )
    preferred_room_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    has_special_accommodation_requirement: Mapped[bool] = mapped_column(default=False, nullable=False)
    special_accommodation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    special_requirement_status: Mapped[RequirementVerificationStatus] = mapped_column(
        Enum(RequirementVerificationStatus), default=RequirementVerificationStatus.NONE, nullable=False
    )
    submitted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    student = relationship("Student", back_populates="applications")
    preferences = relationship(
        "HostelPreference", back_populates="application", cascade="all, delete-orphan",
        order_by="HostelPreference.preference_rank",
    )
    priority_score = relationship("StudentPriorityScore", back_populates="application", uselist=False)


class HostelPreference(Base, TimestampMixin):
    __tablename__ = "hostel_preferences"
    __table_args__ = (
        UniqueConstraint("application_id", "hostel_id", name="uq_hostel_once_per_application"),
        UniqueConstraint("application_id", "preference_rank", name="uq_rank_once_per_application"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"), nullable=False)
    preference_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    application = relationship("Application", back_populates="preferences")
    hostel = relationship("Hostel")
