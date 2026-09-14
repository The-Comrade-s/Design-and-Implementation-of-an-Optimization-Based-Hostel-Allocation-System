from __future__ import annotations

import streamlit as st

from app.core.database import get_session
from app.core.exceptions import HOSException
from app.services import allocation_service, dashboard_service
from app.utils.session import current_user_id


def render() -> None:
    st.header("Allocation Review, Approval & Publication")

    with get_session() as session:
        runs = dashboard_service.optimization_run_history(session)
    if not runs:
        st.info("No optimization runs are available. Run the optimizer first.")
        return

    run_map = {f"Run #{r.id} — {r.academic_session} — {r.status.value}": r.id for r in runs}
    selected_run_label = st.selectbox("Optimization Run", list(run_map.keys()))
    run_id = run_map[selected_run_label]

    with get_session() as session:
        allocations = allocation_service.list_proposed_allocations(session, run_id)
        rows = [{
            "ID": a.id, "Student": a.student.student_id, "Name": a.student.full_name,
            "Hostel": a.hostel.name, "Room": a.room.room_number, "Bed": a.bed_space.bed_identifier,
            "Score": round(a.allocation_score, 2), "Pref Rank": a.preference_rank, "Status": a.status.value,
        } for a in allocations]

    st.dataframe(rows, use_container_width=True, hide_index=True)

    if not allocations:
        st.info("No proposed allocations for this run.")
        return

    st.subheader("Bulk Actions")
    proposed_ids = [a.id for a in allocations if a.status.value in ("PROPOSED", "UNDER_REVIEW")]
    approved_ids = [a.id for a in allocations if a.status.value == "APPROVED"]

    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"Approve All Proposed ({len(proposed_ids)})", disabled=not proposed_ids):
            with get_session() as session:
                ok, errors = allocation_service.bulk_approve(session, proposed_ids, current_user_id())
            st.success(f"Approved {len(ok)} allocation(s).")
            if errors:
                st.warning(f"{len(errors)} could not be approved.")
            st.rerun()
    with col2:
        if st.button(f"Publish All Approved ({len(approved_ids)})", disabled=not approved_ids):
            with get_session() as session:
                ok, errors = allocation_service.bulk_publish(session, approved_ids, current_user_id())
            st.success(f"Published {len(ok)} allocation(s).")
            if errors:
                st.warning(f"{len(errors)} could not be published.")
            st.rerun()

    st.divider()
    st.subheader("Individual Allocation Actions")
    alloc_map = {f"{a.student.student_id} — {a.hostel.name}/{a.room.room_number} — {a.status.value}": a.id
                 for a in allocations}
    selected_label = st.selectbox("Select allocation", list(alloc_map.keys()))
    alloc_id = alloc_map[selected_label]

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Approve"):
            try:
                with get_session() as session:
                    allocation_service.approve_allocation(session, alloc_id, current_user_id())
                st.success("Allocation approved.")
                st.rerun()
            except HOSException as exc:
                st.error(exc.message)
    with c2:
        if st.button("Publish"):
            try:
                with get_session() as session:
                    allocation_service.publish_allocation(session, alloc_id, current_user_id())
                st.success("Allocation published.")
                st.rerun()
            except HOSException as exc:
                st.error(exc.message)
    with c3:
        release_reason = st.text_input("Release reason", key="release_reason")
        if st.button("Release"):
            try:
                with get_session() as session:
                    allocation_service.release_allocation(session, alloc_id, release_reason, current_user_id())
                st.success("Allocation released.")
                st.rerun()
            except HOSException as exc:
                st.error(exc.message)

    st.divider()
    st.subheader("Unallocated Students")
    with get_session() as session:
        reasons = dashboard_service.unallocated_reasons_breakdown(session, run_id)
    st.write(reasons or "None.")
