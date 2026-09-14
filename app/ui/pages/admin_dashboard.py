from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.core.database import get_session
from app.services import dashboard_service


def render() -> None:
    st.header("Admin Dashboard")

    with get_session() as session:
        kpis = dashboard_service.admin_kpis(session)
        occupancy = dashboard_service.hostel_occupancy_report(session)
        app_breakdown = dashboard_service.application_status_breakdown(session)

    cols = st.columns(4)
    labels = [
        ("Total Students", kpis["total_students"]),
        ("Total Applications", kpis["total_applications"]),
        ("Eligible Applicants", kpis["eligible_applicants"]),
        ("Total Bed Spaces", kpis["total_bed_spaces"]),
        ("Usable Bed Spaces", kpis["usable_bed_spaces"]),
        ("Allocated", kpis["allocated"]),
        ("Unallocated", kpis["unallocated"]),
        ("Occupancy Rate", f"{kpis['occupancy_rate']}%"),
    ]
    for i, (label, value) in enumerate(labels):
        with cols[i % 4]:
            st.metric(label, value)

    st.divider()
    st.subheader("Hostel Capacity Overview")
    if occupancy:
        df = pd.DataFrame(occupancy)
        st.dataframe(df, use_container_width=True, hide_index=True)
        fig = px.bar(df, x="hostel", y=["usable_capacity", "total_capacity"], barmode="group",
                     title="Hostel Capacity vs Usable Capacity")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hostels have been configured yet.")

    st.divider()
    st.subheader("Application Status Breakdown")
    if app_breakdown:
        df2 = pd.DataFrame({"status": list(app_breakdown.keys()), "count": list(app_breakdown.values())})
        fig2 = px.pie(df2, names="status", values="count", title="Applications by Status")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No applications found for the selected academic session.")
