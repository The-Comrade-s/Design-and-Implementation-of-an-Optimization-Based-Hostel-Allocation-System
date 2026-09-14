from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
from app.core.logging_config import get_logger
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.audit_service import log_action

logger = get_logger("auth_service")


def register_user(session: Session, email: str, password: str, role: UserRole) -> User:
    repo = UserRepository(session)
    email = email.lower().strip()
    if not email or "@" not in email:
        raise ValidationError("A valid email address is required.")
    if repo.get_by_email(email):
        raise ConflictError("An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(password), role=role, is_active=True)
    repo.add(user)
    log_action(session, user_id=user.id, action="USER_CREATED", entity_type="User", entity_id=user.id)
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    repo = UserRepository(session)
    user = repo.get_by_email(email.lower().strip())
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        logger.warning("Failed login attempt for %s", email)
        if user:
            log_action(session, user_id=user.id, action="LOGIN", description="Failed login attempt")
        raise AuthenticationError("Invalid email or password.")
    log_action(session, user_id=user.id, action="LOGIN", description="Successful login")
    return user
