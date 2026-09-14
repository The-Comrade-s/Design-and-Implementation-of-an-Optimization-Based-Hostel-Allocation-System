from __future__ import annotations

from sqlalchemy import select
import streamlit as st

from app.core.database import get_session
from app.models.notification import Notification
from app.services import allocation_service, student_service
from app.utils.session import current_user_id


def render() -> None:
    st.header("My Allocation")

    with get_session() as session:
        student = student_service.get_student_by_user(session, current_user_id())
        if not student:
            st.warning("No student profile is linked to your account.")
            return

        allocation = allocation_service.get_published_allocation_for_student(
            session, student.id, student.academic_session
        )

        if allocation:
            st.success("Your hostel allocation has been published.")
            st.write({
                "Hostel": allocation.hostel.name,
                "Block": allocation.block.name,
                "Floor": allocation.floor.name,
                "Room": allocation.room.room_number,
                "Bed": allocation.bed_space.bed_identifier,
                "Academic Session": allocation.academic_session,
            })
        else:
            st.info("Your hostel allocation has not been published yet.")

        st.divider()
        st.subheader("Notifications")
        notifications = list(session.scalars(
            select(Notification).where(Notification.user_id == current_user_id())
            .order_by(Notification.created_at.desc())
        ).all())
        if notifications:
            for n in notifications:
                st.write(f"**{n.title}** — {n.message}")
        else:
            st.caption("No notifications yet.")
