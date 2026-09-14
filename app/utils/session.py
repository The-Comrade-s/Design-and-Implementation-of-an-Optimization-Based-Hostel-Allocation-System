"""Streamlit session-state helpers for authentication state."""
from __future__ import annotations

import streamlit as st


def is_authenticated() -> bool:
    return bool(st.session_state.get("user_id"))


def current_user_id() -> int | None:
    return st.session_state.get("user_id")


def current_role() -> str | None:
    return st.session_state.get("role")


def current_email() -> str | None:
    return st.session_state.get("email")


def login_session(user_id: int, role: str, email: str) -> None:
    st.session_state["user_id"] = user_id
    st.session_state["role"] = role
    st.session_state["email"] = email


def logout_session() -> None:
    for key in ("user_id", "role", "email"):
        st.session_state.pop(key, None)


def require_role(*roles: str) -> bool:
    if not is_authenticated():
        st.warning("Please log in to continue.")
        st.stop()
    if current_role() not in roles:
        st.error("You are not authorized to view this page.")
        st.stop()
    return True
