from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PriorityCriterion(Base, TimestampMixin):
    """Configurable weighted criterion (e.g. FINAL_YEAR, DISTANCE)."""
    __tablename__ = "priority_criteria"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    maximum_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PreferenceScoreConfig(Base, TimestampMixin):
    """Configurable score awarded per hostel-preference rank (1st, 2nd, ...)."""
    __tablename__ = "preference_score_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    preference_rank: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PenaltyConfig(Base, TimestampMixin):
    """Configurable soft-constraint penalty (e.g. room-type mismatch)."""
    __tablename__ = "penalty_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    penalty_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RuleSetVersion(Base, TimestampMixin):
    """A snapshot label for the active scoring configuration, used to make
    allocation runs reproducible/auditable."""
    __tablename__ = "rule_set_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_label: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class StudentPriorityScore(Base, TimestampMixin):
    __tablename__ = "student_priority_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), unique=True, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    calculation_version: Mapped[str] = mapped_column(String(30), nullable=False)
    calculated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    incomplete_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    application = relationship("Application", back_populates="priority_score")
    details = relationship("PriorityScoreDetail", back_populates="priority_score", cascade="all, delete-orphan")


class PriorityScoreDetail(Base, TimestampMixin):
    __tablename__ = "priority_score_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    priority_score_id: Mapped[int] = mapped_column(ForeignKey("student_priority_scores.id"), nullable=False, index=True)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("priority_criteria.id"), nullable=False)
    raw_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    weighted_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    priority_score = relationship("StudentPriorityScore", back_populates="details")
    criterion = relationship("PriorityCriterion")
