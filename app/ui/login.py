from __future__ import annotations

import streamlit as st

from app.core.database import get_session
from app.core.exceptions import HOSException
from app.services.auth_service import authenticate
from app.utils.session import login_session


def render_login() -> None:
    st.markdown(
        "<h1 style='text-align:center;margin-bottom:0;'>HOSTEL OPTIMIZATION SYSTEM</h1>"
        "<p style='text-align:center;color:#666;margin-top:4px;'>Institutional Accommodation Management</p>",
        unsafe_allow_html=True,
    )
    st.write("")
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        with st.container(border=True):
            st.subheader("Sign in")
            email = st.text_input("Email / Username")
            password = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True, type="primary"):
                if not email or not password:
                    st.error("Please provide both email and password.")
                    return
                try:
                    with get_session() as session:
                        user = authenticate(session, email, password)
                        login_session(user.id, user.role.value, user.email)
                    st.rerun()
                except HOSException as exc:
                    st.error(exc.message)
                except Exception:  # noqa: BLE001
                    st.error("The operation could not be completed. Please try again.")
