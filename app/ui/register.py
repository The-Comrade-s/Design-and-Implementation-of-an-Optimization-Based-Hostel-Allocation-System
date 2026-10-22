from __future__ import annotations

import streamlit as st

from app.core.database import get_session
from app.core.exceptions import HOSException
from app.models.student import Gender
from app.models.user import UserRole
from app.services import auth_service, student_service
from app.utils.session import login_session


def render_register() -> None:
    st.write("")
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        with st.container(border=True):
            st.subheader("Student Registration")
            st.caption("Create your account, then choose your hostel, room and bed space.")
            with st.form("student_self_registration"):
                first_name = st.text_input("First Name")
                last_name = st.text_input("Last Name")
                student_id = st.text_input("Matric / Student ID")
                gender = st.selectbox("Gender", [g.value for g in Gender])
                department = st.text_input("Department")
                programme = st.text_input("Programme")
                level = st.selectbox("Level", ["100", "200", "300", "400", "500"])
                academic_session = st.text_input("Academic Session", value="2026/2027")
                phone = st.text_input("Phone Number (optional)")
                email = st.text_input("Email (used to log in)")
                password = st.text_input("Password (min 8 characters)", type="password")
                confirm = st.text_input("Confirm Password", type="password")
                submitted = st.form_submit_button("Register", type="primary", use_container_width=True)

            if not submitted:
                return

            required = [first_name, last_name, student_id, department, programme, academic_session, email, password]
            if not all(v and v.strip() for v in required):
                st.error("Please fill in all required fields.")
                return
            if password != confirm:
                st.error("Passwords do not match.")
                return

            try:
                with get_session() as session:
                    user = auth_service.register_user(session, email, password, UserRole.STUDENT)
                    student_service.create_student(
                        session, user_id=user.id, student_id=student_id.strip(),
                        first_name=first_name.strip(), last_name=last_name.strip(),
                        gender=Gender(gender), email=user.email, department=department.strip(),
                        programme=programme.strip(), level=level, academic_session=academic_session.strip(),
                        phone_number=phone.strip() or None, actor_id=user.id,
                    )
                    uid, role, mail = user.id, user.role.value, user.email
                login_session(uid, role, mail)
                st.rerun()
            except HOSException as exc:
                st.error(exc.message)
            except ValueError as exc:  # password length rules from hash_password
                st.error(str(exc))
