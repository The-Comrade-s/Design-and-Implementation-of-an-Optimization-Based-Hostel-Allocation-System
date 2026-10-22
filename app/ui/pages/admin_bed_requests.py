from __future__ import annotations

import streamlit as st

from app.core.database import get_session
from app.core.exceptions import HOSException
from app.models.allocation import AllocationStatus
from app.services import bed_request_service, student_service
from app.utils.session import current_user_id


def _when(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def render() -> None:
    st.header("Student Bed Requests")
    st.caption("Students choose their own hostel, room and bed. Allocate it if they qualify, otherwise decline with a reason.")
    tabs = st.tabs(["Pending Requests", "Decided"])

    with tabs[0]:
        with get_session() as session:
            pending = bed_request_service.list_requests(session, bed_request_service.PENDING_STATUSES)
            rows, options = [], {}
            qualified_ids = []
            for a in pending:
                e = student_service.check_student_eligibility(session, a.student_id)
                if e.eligible:
                    qualified_ids.append(a.id)
                rows.append({
                    "Request ID": a.id, "Student ID": a.student.student_id, "Name": a.student.full_name,
                    "Gender": a.student.gender.value, "Level": a.student.level,
                    "Department": a.student.department,
                    "Hostel": a.hostel.name, "Block": a.block.name, "Floor": a.floor.name,
                    "Room": a.room.room_number, "Bed": a.bed_space.bed_identifier,
                    "Qualified": "Yes" if e.eligible else f"No — {e.reason}",
                    "Requested": _when(a.created_at),
                })
                options[f"#{a.id} — {a.student.student_id} {a.student.full_name} → "
                        f"{a.hostel.name}/{a.room.room_number}/{a.bed_space.bed_identifier}"] = a.id

        if not rows:
            st.info("No pending bed requests.")
        else:
            st.dataframe(rows, use_container_width=True, hide_index=True)

            if st.button(f"Allocate all qualified ({len(qualified_ids)})", disabled=not qualified_ids):
                done, errors = 0, []
                for rid in qualified_ids:
                    try:
                        with get_session() as session:
                            bed_request_service.approve_request(session, rid, current_user_id())
                        done += 1
                    except HOSException as exc:
                        errors.append(f"Request {rid}: {exc.message}")
                st.success(f"Allocated {done} student(s).")
                for err in errors:
                    st.warning(err)
                if not errors:
                    st.rerun()

            st.divider()
            st.subheader("Review one request")
            label = st.selectbox("Select request", list(options.keys()))
            rid = options[label]
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Allocate this bed", type="primary"):
                    try:
                        with get_session() as session:
                            bed_request_service.approve_request(session, rid, current_user_id())
                        st.success("Bed allocated and published to the student.")
                        st.rerun()
                    except HOSException as exc:
                        st.error(exc.message)
            with c2:
                reason = st.text_input("Reason for declining", key=f"decline_reason_{rid}")
                if st.button("Decline request"):
                    try:
                        with get_session() as session:
                            bed_request_service.reject_request(session, rid, reason, current_user_id())
                        st.success("Request declined. The student has been notified.")
                        st.rerun()
                    except HOSException as exc:
                        st.error(exc.message)

    with tabs[1]:
        with get_session() as session:
            decided = bed_request_service.list_requests(
                session, (AllocationStatus.APPROVED, AllocationStatus.PUBLISHED, AllocationStatus.CANCELLED,
                          AllocationStatus.RELEASED),
            )
            rows = [{
                "Request ID": a.id, "Student ID": a.student.student_id, "Name": a.student.full_name,
                "Hostel": a.hostel.name, "Room": a.room.room_number, "Bed": a.bed_space.bed_identifier,
                "Outcome": a.status.value, "Reason": a.release_reason or "",
            } for a in decided]
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("Nothing decided yet.")
