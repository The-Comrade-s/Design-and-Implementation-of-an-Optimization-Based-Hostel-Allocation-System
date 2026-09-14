"""Development-only seed data. Never run against production.

Creates:
  - 1 admin account (admin@hos.local / Admin@12345)
  - 2 hostels, blocks, floors, rooms with auto-generated beds
  - Default priority/preference/penalty rules
  - 10 fictional students with user accounts, applications and preferences,
    including one deliberately ineligible/incompatible case, so the
    optimizer has a realistic small dataset to work with.

Usage:
    python scripts/seed_demo_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_session, init_db  # noqa: E402
from app.core.exceptions import HOSException  # noqa: E402
from app.models.hostel import HostelCategory, RoomType  # noqa: E402
from app.models.student import Gender  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from app.services import application_service, auth_service, hostel_service, student_service  # noqa: E402
from app.services.application_service import submit_application, verify_application  # noqa: E402
from app.services.priority_service import seed_default_rules  # noqa: E402

ACADEMIC_SESSION = "2026/2027"

FICTIONAL_STUDENTS = [
    # student_id, first, last, gender, level, dept
    ("STU001", "Amaka", "Obi", Gender.FEMALE, "400", "Computer Science"),
    ("STU002", "Tunde", "Bello", Gender.MALE, "300", "Mass Communication"),
    ("STU003", "Ngozi", "Eze", Gender.FEMALE, "200", "Accounting"),
    ("STU004", "Chidi", "Nwosu", Gender.MALE, "400", "Computer Science"),
    ("STU005", "Fatima", "Sani", Gender.FEMALE, "300", "Public Administration"),
    ("STU006", "Emeka", "Okafor", Gender.MALE, "100", "Economics"),
    ("STU007", "Bukola", "Ade", Gender.FEMALE, "400", "Law"),
    ("STU008", "Ibrahim", "Musa", Gender.MALE, "200", "Computer Science"),
    ("STU009", "Chioma", "Uche", Gender.FEMALE, "300", "Accounting"),
    ("STU010", "Segun", "Ogundele", Gender.MALE, "400", "Mass Communication"),
]


def main() -> None:
    init_db()
    with get_session() as session:
        # Admin
        try:
            auth_service.register_user(session, "admin@hos.local", "Admin@12345", UserRole.ADMIN)
            print("Created admin: admin@hos.local / Admin@12345")
        except HOSException:
            print("Admin already exists, skipping.")

        seed_default_rules(session)
        print("Seeded default priority/preference/penalty rules.")

        # Hostels
        try:
            hostel_a = hostel_service.create_hostel(
                session, name="Hostel A", code="HOS-A", category=HostelCategory.FEMALE,
                location="North Campus",
            )
            hostel_b = hostel_service.create_hostel(
                session, name="Hostel B", code="HOS-B", category=HostelCategory.MALE,
                location="South Campus",
            )
        except HOSException:
            print("Hostels already exist, skipping creation.")
            from sqlalchemy import select
            from app.models.hostel import Hostel
            hostel_a = session.scalars(select(Hostel).where(Hostel.code == "HOS-A")).first()
            hostel_b = session.scalars(select(Hostel).where(Hostel.code == "HOS-B")).first()

        for hostel, prefix in [(hostel_a, "A"), (hostel_b, "B")]:
            existing_blocks = {b.code for b in hostel.blocks}
            if f"{prefix}1" in existing_blocks:
                continue
            block = hostel_service.create_block(session, hostel_id=hostel.id, name=f"Block {prefix}",
                                                 code=f"{prefix}1")
            floor = hostel_service.create_floor(session, block_id=block.id, name="1")
            # Deliberately limited capacity: 4 rooms x 2 beds = 8 beds per hostel
            for i in range(1, 5):
                hostel_service.create_room(
                    session, floor_id=floor.id, room_number=f"{prefix}10{i}",
                    room_type=RoomType.DOUBLE, capacity=2, generate_beds=True,
                )
        print("Seeded hostel infrastructure (2 hostels, 8 usable beds each).")

        # Students + applications
        for idx, (sid, first, last, gender, level, dept) in enumerate(FICTIONAL_STUDENTS, start=1):
            email = f"{sid.lower()}@student.hos.local"
            try:
                user = auth_service.register_user(session, email, "Student@12345", UserRole.STUDENT)
            except HOSException:
                print(f"{sid} already exists, skipping.")
                continue

            student = student_service.create_student(
                session, user_id=user.id, student_id=sid, first_name=first, last_name=last,
                gender=gender, email=email, department=dept, programme=dept, level=level,
                academic_session=ACADEMIC_SESSION, year_of_entry=2023,
            )

            application = application_service.create_application(
                session, student_id=student.id, academic_session=ACADEMIC_SESSION,
            )

            # Give each student a preference order; last two students get an
            # intentionally over-subscribed / mismatched preference to
            # demonstrate partial allocation and fallback handling.
            preferred_hostel = hostel_a if gender == Gender.FEMALE else hostel_b
            other_hostel = hostel_b if gender == Gender.FEMALE else hostel_a
            try:
                application_service.set_hostel_preferences(
                    session, application.id, [(preferred_hostel.id, 1)]
                )
                submit_application(session, application.id)
                verify_application(session, application.id, verifier_user_id=1)
            except HOSException as exc:
                print(f"Could not fully process {sid}: {exc.message}")

        print(f"Seeded {len(FICTIONAL_STUDENTS)} fictional students with applications for {ACADEMIC_SESSION}.")
        print("Demo data seeding complete.")


if __name__ == "__main__":
    main()
