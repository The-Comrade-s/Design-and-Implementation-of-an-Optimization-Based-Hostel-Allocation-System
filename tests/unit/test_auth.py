from __future__ import annotations

import pytest

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import hash_password, verify_password
from app.models.user import UserRole
from app.services.auth_service import authenticate, register_user


def test_hash_and_verify_password():
    hashed = hash_password("Str0ngPass!")
    assert hashed != "Str0ngPass!"
    assert verify_password("Str0ngPass!", hashed)
    assert not verify_password("WrongPass!", hashed)


def test_password_too_short_rejected():
    with pytest.raises(ValueError):
        hash_password("short")


def test_register_and_authenticate(session):
    user = register_user(session, "admin@example.com", "Admin@12345", UserRole.ADMIN)
    assert user.id is not None
    assert user.role == UserRole.ADMIN

    authenticated = authenticate(session, "admin@example.com", "Admin@12345")
    assert authenticated.id == user.id


def test_duplicate_registration_rejected(session):
    register_user(session, "dup@example.com", "Password123", UserRole.STUDENT)
    with pytest.raises(ConflictError):
        register_user(session, "dup@example.com", "Password123", UserRole.STUDENT)


def test_login_failure_wrong_password(session):
    register_user(session, "user@example.com", "Correct123", UserRole.STUDENT)
    with pytest.raises(AuthenticationError):
        authenticate(session, "user@example.com", "Wrong123")


def test_login_failure_unknown_user(session):
    with pytest.raises(AuthenticationError):
        authenticate(session, "nobody@example.com", "whatever123")
