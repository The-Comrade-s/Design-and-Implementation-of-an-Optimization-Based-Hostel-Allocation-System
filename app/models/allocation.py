from __future__ import annotations

import enum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class AllocationStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"
    RELEASED = "RELEASED"


class AllocationResult(Base, TimestampMixin):
    """Proposed / approved / published allocation record.

    Only one row per (student, academic_session) may be in an ACTIVE
    state (PROPOSED..PUBLISHED) at a time; enforced in the service layer
    plus a partial application-level check (SQLite/Postgres portability
    limits a DB-level partial unique index here).
    """
    __tablename__ = "allocation_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    optimization_run_id: Mapped[int | None] = mapped_column(ForeignKey("optimization_runs.id"), nullable=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    academic_session: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"), nullable=False)
    block_id: Mapped[int] = mapped_column(ForeignKey("blocks.id"), nullable=False)
    floor_id: Mapped[int] = mapped_column(ForeignKey("floors.id"), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    bed_space_id: Mapped[int] = mapped_column(ForeignKey("bed_spaces.id"), nullable=False, index=True)
    allocation_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    preference_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AllocationStatus] = mapped_column(Enum(AllocationStatus), default=AllocationStatus.PROPOSED, nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    student = relationship("Student")
    application = relationship("Application")
    hostel = relationship("Hostel")
    block = relationship("Block")
    floor = relationship("Floor")
    room = relationship("Room")
    bed_space = relationship("BedSpace")
    optimization_run = relationship("OptimizationRun", back_populates="results")
    history = relationship("AllocationHistory", back_populates="allocation", cascade="all, delete-orphan")


class AllocationHistory(Base, TimestampMixin):
    """Immutable trail of allocation changes (override, release, reassign)."""
    __tablename__ = "allocation_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    allocation_id: Mapped[int] = mapped_column(ForeignKey("allocation_results.id"), nullable=False, index=True)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    allocation = relationship("AllocationResult", back_populates="history")


class WaitlistEntry(Base, TimestampMixin):
    __tablename__ = "waitlist_entries"
    __table_args__ = (UniqueConstraint("student_id", "academic_session", name="uq_waitlist_student_session"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    academic_session: Mapped[str] = mapped_column(String(20), nullable=False)
    priority_position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
