from __future__ import annotations

import enum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class OptimizationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIME_LIMIT = "TIME_LIMIT"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OptimizationRun(Base, TimestampMixin):
    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_session: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[OptimizationStatus] = mapped_column(
        Enum(OptimizationStatus), default=OptimizationStatus.PENDING, nullable=False
    )
    algorithm: Mapped[str] = mapped_column(String(50), default="CP-SAT", nullable=False)
    solver: Mapped[str] = mapped_column(String(50), default="OR-Tools CP-SAT", nullable=False)
    applicant_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bed_space_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allocated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unallocated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    objective_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    execution_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    rule_set_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    solver_time_limit_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    results = relationship("AllocationResult", back_populates="optimization_run")
    unallocated = relationship("UnallocatedRecord", back_populates="optimization_run")


class UnallocatedReason(str, enum.Enum):
    NO_AVAILABLE_BED = "NO_AVAILABLE_BED"
    NO_COMPATIBLE_HOSTEL = "NO_COMPATIBLE_HOSTEL"
    NO_VALID_ASSIGNMENT = "NO_VALID_ASSIGNMENT"
    CAPACITY_EXHAUSTED = "CAPACITY_EXHAUSTED"
    INELIGIBLE = "INELIGIBLE"
    OTHER = "OTHER"


class UnallocatedRecord(Base, TimestampMixin):
    __tablename__ = "unallocated_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    optimization_run_id: Mapped[int] = mapped_column(ForeignKey("optimization_runs.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    reason: Mapped[UnallocatedReason] = mapped_column(Enum(UnallocatedReason), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    optimization_run = relationship("OptimizationRun", back_populates="unallocated")
    student = relationship("Student")
    application = relationship("Application")
