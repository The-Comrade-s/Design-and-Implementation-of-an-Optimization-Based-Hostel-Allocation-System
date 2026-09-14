from __future__ import annotations

import pandas as pd
import streamlit as st

from app.core.database import get_session
from app.services import dashboard_service


def render() -> None:
    st.header("Reports & Analytics")
    academic_session = st.text_input("Academic Session for report", value="2026/2027")

    tabs = st.tabs(["Hostel Occupancy", "Preference Satisfaction", "Unallocated", "Export"])

    with tabs[0]:
        with get_session() as session:
            data = dashboard_service.hostel_occupancy_report(session)
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[1]:
        with get_session() as session:
            sat = dashboard_service.preference_satisfaction(session, academic_session)
        st.write({k: v for k, v in sat.items() if not k.startswith("_")})

    with tabs[2]:
        with get_session() as session:
            reasons = dashboard_service.unallocated_reasons_breakdown(session)
        st.write(reasons or "No unallocated records.")

    with tabs[3]:
        with get_session() as session:
            data = dashboard_service.hostel_occupancy_report(session)
        df = pd.DataFrame(data)
        if not df.empty:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download Hostel Occupancy (CSV)", csv, "hostel_occupancy.csv", "text/csv")
        else:
            st.info("No data available to export yet.")
