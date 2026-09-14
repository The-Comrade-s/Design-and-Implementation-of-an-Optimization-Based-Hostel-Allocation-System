from __future__ import annotations

import streamlit as st

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import HOSException
from app.services import dashboard_service
from app.services.optimization_service import execute_optimization
from app.utils.session import current_user_id


def render() -> None:
    st.header("Optimization Engine")

    academic_session = st.text_input("Academic Session", value="2026/2027")
    time_limit = st.number_input("Solver Time Limit (seconds)", min_value=5, max_value=600,
                                  value=settings.OPTIMIZATION_TIME_LIMIT_SECONDS)

    if st.button("Run Optimization", type="primary"):
        with st.spinner("Preparing applicants and accommodation, then running the solver..."):
            try:
                with get_session() as session:
                    outcome = execute_optimization(
                        session, academic_session=academic_session,
                        time_limit_seconds=int(time_limit), actor_id=current_user_id(),
                    )
                st.success("Optimization run complete.")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Applicants", outcome.applicant_count)
                c2.metric("Allocated", outcome.allocated_count)
                c3.metric("Unallocated", outcome.unallocated_count)
                c4.metric("Solver Status", outcome.status.value)
                st.metric("Objective Score", outcome.objective_score if outcome.objective_score is not None else "N/A")
                st.metric("Execution Time (s)", round(outcome.execution_time, 2))
            except HOSException as exc:
                st.error(exc.message)

    st.divider()
    st.subheader("Optimization Run History")
    with get_session() as session:
        runs = dashboard_service.optimization_run_history(session)
        rows = [{
            "ID": r.id, "Session": r.academic_session, "Status": r.status.value,
            "Applicants": r.applicant_count, "Beds": r.bed_space_count,
            "Allocated": r.allocated_count, "Unallocated": r.unallocated_count,
            "Objective": r.objective_score, "Exec Time (s)": round(r.execution_time or 0, 2),
            "Rule Set": r.rule_set_version,
        } for r in runs]
    st.dataframe(rows, use_container_width=True, hide_index=True)
