from __future__ import annotations

import os
import streamlit as st

for k, v in st.secrets.items():
    os.environ[k] = str(v)

from app.core.database import check_database_connection, init_db
from app.core.logging_config import configure_logging, get_logger
from app.ui.login import render_login
from app.utils.session import current_email, current_role, is_authenticated, logout_session

configure_logging()
logger = get_logger("main")

st.set_page_config(page_title="Hostel Optimization System", layout="wide")


def _bootstrap() -> None:
    if not st.session_state.get("_bootstrapped"):
        try:
            init_db()
            if not check_database_connection():
                st.error("Database connection failed. Please check configuration.")
                st.stop()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Startup failure")
            st.error("The application could not start. Please check the server configuration.")
            st.stop()
        st.session_state["_bootstrapped"] = True


def _render_admin() -> None:
    from app.ui.pages import (
        admin_allocations, admin_applications, admin_dashboard,
        admin_hostels, admin_optimization, admin_priority_rules, admin_reports,
    )

    page = st.sidebar.radio(
        "Admin Navigation",
        ["Dashboard", "Hostel Infrastructure", "Students & Applications",
         "Priority Rules", "Optimization", "Allocation Review", "Reports"],
    )
    pages = {
        "Dashboard": admin_dashboard.render,
        "Hostel Infrastructure": admin_hostels.render,
        "Students & Applications": admin_applications.render,
        "Priority Rules": admin_priority_rules.render,
        "Optimization": admin_optimization.render,
        "Allocation Review": admin_allocations.render,
        "Reports": admin_reports.render,
    }
    pages[page]()


def _render_student() -> None:
    from app.ui.pages import student_allocation, student_application

    page = st.sidebar.radio("Student Navigation", ["My Application", "My Allocation"])
    pages = {
        "My Application": student_application.render,
        "My Allocation": student_allocation.render,
    }
    pages[page]()


def main() -> None:
    _bootstrap()

    if not is_authenticated():
        render_login()
        return

    st.sidebar.markdown(f"**Signed in as:** {current_email()}")
    st.sidebar.markdown(f"**Role:** {current_role()}")
    if st.sidebar.button("Logout"):
        logout_session()
        st.rerun()
    st.sidebar.divider()

    role = current_role()
    if role == "ADMIN":
        _render_admin()
    elif role == "STUDENT":
        _render_student()
    else:
        st.error("Unrecognized role. Please contact an administrator.")


if __name__ == "__main__":
    main()
