"""Password hashing and other security utilities.

Uses bcrypt directly (rather than through passlib) for secure password
hashing. Never store or log plaintext passwords.
"""
from __future__ import annotations

import secrets

import bcrypt


def hash_password(plain_password: str) -> str:
    if not plain_password or len(plain_password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(plain_password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes long.")
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False


def generate_reference(prefix: str, sequence: int, session_label: str) -> str:
    """Generate a collision-resistant, sequential reference such as
    HOS-2026-000001. Uses a DB-provided sequence number rather than
    random values, so callers must supply a real sequence value.
    """
    year = session_label.split("/")[0] if "/" in session_label else session_label
    return f"{prefix}-{year}-{sequence:06d}"


def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token (e.g. for CSRF-like
    protections or one-off secure identifiers). Never used for passwords.
    """
    return secrets.token_urlsafe(length)
