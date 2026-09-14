"""Securely create the initial administrator account.

Usage:
    python scripts/create_admin.py

Prompts for email and password interactively. Never hard-codes a
password, and refuses to run if an admin with the given email already
exists.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_session, init_db  # noqa: E402
from app.core.exceptions import HOSException  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from app.services.auth_service import register_user  # noqa: E402


def main() -> None:
    init_db()
    email = input("Administrator email: ").strip()
    password = getpass.getpass("Administrator password (min 8 characters): ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    try:
        with get_session() as session:
            user = register_user(session, email, password, UserRole.ADMIN)
        print(f"Administrator account created: {user.email}")
    except HOSException as exc:
        print(f"Error: {exc.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
