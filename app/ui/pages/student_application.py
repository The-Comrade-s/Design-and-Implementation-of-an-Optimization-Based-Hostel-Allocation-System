from __future__ import annotations

import streamlit as st

from app.core.database import get_session
from app.core.exceptions import HOSException
from app.services import application_service, hostel_service, student_service
from app.utils.session import current_user_id


def render() -> None:
    st.header("My Hostel Application")

    with get_session() as session:
        student = student_service.get_student_by_user(session, current_user_id())
        if not student:
            st.warning("No student profile is linked to your account. Contact an administrator.")
            return
        student_id = student.id
        academic_session = student.academic_session

        st.subheader("Profile")
        st.write({
            "Student ID": student.student_id, "Name": student.full_name,
            "Department": student.department, "Programme": student.programme,
            "Level": student.level, "Academic Session": student.academic_session,
        })

        eligibility = student_service.check_student_eligibility(session, student_id)
        st.info(f"Eligibility: {eligibility.status.value} — {eligibility.reason}")

        application = application_service.get_student_application(session, student_id, academic_session)
        hostels = hostel_service.list_hostels(session)

    if not application:
        if st.button("Start Application", type="primary"):
            try:
                with get_session() as session:
                    application_service.create_application(
                        session, student_id=student_id, academic_session=academic_session,
                        actor_id=current_user_id(),
                    )
                st.success("Application started. Set your hostel preferences below.")
                st.rerun()
            except HOSException as exc:
                st.error(exc.message)
        return

    st.divider()
    st.subheader(f"Application {application.application_reference}")
    st.write(f"Status: **{application.status.value}**")

    if application.status.value == "DRAFT":
        hostel_options = {f"{h.name} ({h.code})": h.id for h in hostels if h.status.value == "ACTIVE"}
        if not hostel_options:
            st.info("No active hostels are available for selection yet.")
        else:
            st.write("Select your hostel preferences, in order of priority:")
            choice_1 = st.selectbox("1st Choice", ["--"] + list(hostel_options.keys()), key="c1")
            choice_2 = st.selectbox("2nd Choice", ["--"] + list(hostel_options.keys()), key="c2")
            choice_3 = st.selectbox("3rd Choice", ["--"] + list(hostel_options.keys()), key="c3")

            if st.button("Save Preferences"):
                ranks = []
                for rank, choice in enumerate([choice_1, choice_2, choice_3], start=1):
                    if choice != "--":
                        ranks.append((hostel_options[choice], rank))
                try:
                    with get_session() as session:
                        application_service.set_hostel_preferences(session, application.id, ranks)
                    st.success("Preferences saved.")
                    st.rerun()
                except HOSException as exc:
                    st.error(exc.message)

            if application.preferences and st.button("Submit Application", type="primary"):
                try:
                    with get_session() as session:
                        application_service.submit_application(session, application.id, current_user_id())
                    st.success("Application submitted for review.")
                    st.rerun()
                except HOSException as exc:
                    st.error(exc.message)
    else:
        st.write("Preferences:")
        for p in application.preferences:
            st.write(f"{p.preference_rank}. {p.hostel.name}")
        st.write("Allocation Status: Not yet available." if application.status.value != "VERIFIED"
                  else "Your application has been verified. Await allocation publication.")
