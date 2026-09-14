from __future__ import annotations

import enum

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class StudentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    GRADUATED = "GRADUATED"
    SUSPENDED = "SUSPENDED"
    WITHDRAWN = "WITHDRAWN"


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[Gender] = mapped_column(Enum(Gender), nullable=False)
    date_of_birth: Mapped[Date | None] = mapped_column(Date, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    faculty: Mapped[str | None] = mapped_column(String(150), nullable=True)
    department: Mapped[str] = mapped_column(String(150), nullable=False)
    programme: Mapped[str] = mapped_column(String(150), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    academic_session: Mapped[str] = mapped_column(String(20), nullable=False)
    year_of_entry: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[StudentStatus] = mapped_column(Enum(StudentStatus), default=StudentStatus.ACTIVE, nullable=False)

    user = relationship("User", back_populates="student")
    applications = relationship("Application", back_populates="student")

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)
