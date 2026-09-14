from __future__ import annotations

import streamlit as st

from app.core.database import get_session
from app.core.exceptions import HOSException
from app.models.application import ApplicationStatus
from app.models.user import UserRole
from app.services import application_service, auth_service, student_service
from app.models.student import Gender
from app.utils.session import current_user_id


def render() -> None:
    st.header("Students & Applications")
    tabs = st.tabs(["Register Student", "Applications Review", "Statistics"])

    with tabs[0]:
        st.subheader("Register a New Student")
        with st.form("register_student"):
            email = st.text_input("Login Email")
            password = st.text_input("Temporary Password", type="password")
            student_id = st.text_input("Student ID")
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            gender = st.selectbox("Gender", [g.value for g in Gender])
            department = st.text_input("Department")
            programme = st.text_input("Programme")
            level = st.text_input("Level (e.g. 300)")
            academic_session = st.text_input("Academic Session (e.g. 2026/2027)")
            submitted = st.form_submit_button("Register Student", type="primary")
            if submitted:
                try:
                    with get_session() as session:
                        user = auth_service.register_user(session, email, password, UserRole.STUDENT)
                        student_service.create_student(
                            session, user_id=user.id, student_id=student_id, first_name=first_name,
                            last_name=last_name, gender=Gender(gender), email=email, department=department,
                            programme=programme, level=level, academic_session=academic_session,
                            actor_id=current_user_id(),
                        )
                    st.success(f"Student {student_id} registered.")
                except HOSException as exc:
                    st.error(exc.message)

    with tabs[1]:
        st.subheader("Review Applications")
        status_filter = st.selectbox("Filter by status", ["ALL"] + [s.value for s in ApplicationStatus])
        with get_session() as session:
            apps = application_service.list_applications(
                session, status=None if status_filter == "ALL" else ApplicationStatus(status_filter)
            )
            rows = [{
                "ID": a.id, "Reference": a.application_reference, "Student": a.student.full_name,
                "Session": a.academic_session, "Status": a.status.value,
                "Eligibility": a.eligibility_status.value, "Preferences": len(a.preferences),
            } for a in apps]
        st.dataframe(rows, use_container_width=True, hide_index=True)

        if apps:
            app_map = {f"{a.application_reference} — {a.student.full_name}": a.id for a in apps}
            selected = st.selectbox("Select application", list(app_map.keys()))
            app_id = app_map[selected]
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Verify Application", type="primary"):
                    try:
                        with get_session() as session:
                            application_service.verify_application(session, app_id, current_user_id())
                        st.success("Application verified.")
                        st.rerun()
                    except HOSException as exc:
                        st.error(exc.message)
            with col2:
                reason = st.text_input("Rejection reason", key=f"reason_{app_id}")
                if st.button("Reject Application"):
                    try:
                        with get_session() as session:
                            application_service.reject_application(session, app_id, reason, current_user_id())
                        st.success("Application rejected.")
                        st.rerun()
                    except HOSException as exc:
                        st.error(exc.message)

    with tabs[2]:
        with get_session() as session:
            apps = application_service.list_applications(session)
        counts = {}
        for a in apps:
            counts[a.status.value] = counts.get(a.status.value, 0) + 1
        st.write(counts or "No applications yet.")
