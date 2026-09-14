from __future__ import annotations

from sqlalchemy import select
import streamlit as st

from app.core.database import get_session
from app.models.priority import PenaltyConfig, PreferenceScoreConfig, PriorityCriterion
from app.services.priority_service import seed_default_rules


def render() -> None:
    st.header("Priority Rules & Scoring Configuration")

    with get_session() as session:
        criteria = list(session.scalars(select(PriorityCriterion)).all())
        if not criteria:
            seed_default_rules(session)
            criteria = list(session.scalars(select(PriorityCriterion)).all())
        prefs = list(session.scalars(select(PreferenceScoreConfig)).all())
        penalties = list(session.scalars(select(PenaltyConfig)).all())

        st.subheader("Priority Criteria")
        rows = [{"Code": c.code, "Name": c.name, "Weight": c.weight, "Max Score": c.maximum_score,
                 "Active": c.is_active} for c in criteria]
        st.dataframe(rows, use_container_width=True, hide_index=True)

        crit_map = {c.code: c for c in criteria}
        selected_code = st.selectbox("Edit criterion", list(crit_map.keys()))
        crit = crit_map[selected_code]
        new_weight = st.number_input("Weight", value=float(crit.weight), key="weight_edit")
        new_active = st.checkbox("Active", value=crit.is_active, key="active_edit")
        if st.button("Save Criterion"):
            crit.weight = new_weight
            crit.is_active = new_active
            session.flush()
            st.success("Criterion updated.")
            st.rerun()

        st.divider()
        st.subheader("Hostel Preference Scores")
        st.dataframe([{"Rank": p.preference_rank, "Score": p.score, "Active": p.is_active} for p in prefs],
                     use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Penalties")
        st.dataframe([{"Code": p.code, "Value": p.penalty_value, "Active": p.is_active} for p in penalties],
                     use_container_width=True, hide_index=True)
