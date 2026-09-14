from __future__ import annotations

import streamlit as st

from app.core.database import get_session
from app.core.exceptions import HOSException
from app.models.hostel import AccommodationStatus, HostelCategory, RoomType
from app.services import hostel_service
from app.utils.session import current_user_id


def render() -> None:
    st.header("Hostel Infrastructure Management")

    tabs = st.tabs(["Hostels", "Blocks", "Floors", "Rooms & Beds", "Structure View"])

    with tabs[0]:
        st.subheader("Create Hostel")
        with st.form("create_hostel"):
            name = st.text_input("Name")
            code = st.text_input("Code")
            category = st.selectbox("Category", [c.value for c in HostelCategory])
            location = st.text_input("Location", value="")
            description = st.text_area("Description", value="")
            submitted = st.form_submit_button("Create Hostel", type="primary")
            if submitted:
                try:
                    with get_session() as session:
                        hostel_service.create_hostel(
                            session, name=name, code=code, category=HostelCategory(category),
                            description=description or None, location=location or None,
                            actor_id=current_user_id(),
                        )
                    st.success(f"Hostel '{name}' created.")
                    st.rerun()
                except HOSException as exc:
                    st.error(exc.message)

        st.subheader("Existing Hostels")
        with get_session() as session:
            hostels = hostel_service.list_hostels(session)
            rows = [{"ID": h.id, "Name": h.name, "Code": h.code, "Category": h.category.value,
                     "Status": h.status.value, "Location": h.location} for h in hostels]
        st.dataframe(rows, use_container_width=True, hide_index=True)

        if hostels:
            st.subheader("Update Hostel Status")
            hostel_map = {f"{h.name} ({h.code})": h.id for h in hostels}
            selected = st.selectbox("Select hostel", list(hostel_map.keys()))
            new_status = st.selectbox("New status", [s.value for s in AccommodationStatus])
            if st.button("Update Status"):
                try:
                    with get_session() as session:
                        hostel_service.update_hostel_status(
                            session, hostel_map[selected], AccommodationStatus(new_status), current_user_id()
                        )
                    st.success("Hostel status updated.")
                    st.rerun()
                except HOSException as exc:
                    st.error(exc.message)

    with tabs[1]:
        st.subheader("Create Block")
        with get_session() as session:
            hostels = hostel_service.list_hostels(session)
        if not hostels:
            st.info("Create a hostel first.")
        else:
            hostel_map = {f"{h.name} ({h.code})": h.id for h in hostels}
            with st.form("create_block"):
                hostel_label = st.selectbox("Hostel", list(hostel_map.keys()))
                name = st.text_input("Block Name")
                code = st.text_input("Block Code")
                description = st.text_area("Description", value="", key="block_desc")
                submitted = st.form_submit_button("Create Block", type="primary")
                if submitted:
                    try:
                        with get_session() as session:
                            hostel_service.create_block(
                                session, hostel_id=hostel_map[hostel_label], name=name, code=code,
                                description=description or None, actor_id=current_user_id(),
                            )
                        st.success(f"Block '{name}' created.")
                        st.rerun()
                    except HOSException as exc:
                        st.error(exc.message)

    with tabs[2]:
        st.subheader("Create Floor")
        with get_session() as session:
            hostels = hostel_service.list_hostels(session)
            blocks = []
            for h in hostels:
                blocks.extend(h.blocks)
        if not blocks:
            st.info("Create a block first.")
        else:
            block_map = {f"{b.hostel.name} / {b.name} ({b.code})": b.id for b in blocks}
            with st.form("create_floor"):
                block_label = st.selectbox("Block", list(block_map.keys()))
                name = st.text_input("Floor Name/Number")
                submitted = st.form_submit_button("Create Floor", type="primary")
                if submitted:
                    try:
                        with get_session() as session:
                            hostel_service.create_floor(
                                session, block_id=block_map[block_label], name=name, actor_id=current_user_id()
                            )
                        st.success(f"Floor '{name}' created.")
                        st.rerun()
                    except HOSException as exc:
                        st.error(exc.message)

    with tabs[3]:
        st.subheader("Create Room (with automatic bed-space generation)")
        with get_session() as session:
            hostels = hostel_service.list_hostels(session)
            floors = []
            for h in hostels:
                for b in h.blocks:
                    for f in b.floors:
                        floors.append(f)
        if not floors:
            st.info("Create a floor first.")
        else:
            floor_map = {f"{fl.block.hostel.name} / {fl.block.name} / {fl.name}": fl.id for fl in floors}
            with st.form("create_room"):
                floor_label = st.selectbox("Floor", list(floor_map.keys()))
                room_number = st.text_input("Room Number")
                room_type = st.selectbox("Room Type", [t.value for t in RoomType])
                capacity = st.number_input("Capacity", min_value=1, max_value=20, value=4)
                generate_beds = st.checkbox("Generate Bed Spaces Automatically", value=True)
                submitted = st.form_submit_button("Create Room", type="primary")
                if submitted:
                    try:
                        with get_session() as session:
                            hostel_service.create_room(
                                session, floor_id=floor_map[floor_label], room_number=room_number,
                                room_type=RoomType(room_type), capacity=int(capacity),
                                generate_beds=generate_beds, actor_id=current_user_id(),
                            )
                        st.success(f"Room '{room_number}' created with {capacity} bed space(s).")
                        st.rerun()
                    except HOSException as exc:
                        st.error(exc.message)

    with tabs[4]:
        st.subheader("Hostel Structure")
        with get_session() as session:
            hostels = hostel_service.list_hostels(session)
            for h in hostels:
                with st.expander(f"{h.name} ({h.code}) — {h.category.value} — {h.status.value}"):
                    for b in h.blocks:
                        st.markdown(f"**Block: {b.name}**")
                        for fl in b.floors:
                            room_lines = [f"- {r.room_number} — {len(r.bed_spaces)} bed(s), {r.room_type.value}, {r.status.value}"
                                          for r in fl.rooms]
                            st.markdown(f"*Floor {fl.name}*")
                            if room_lines:
                                st.markdown("\n".join(room_lines))
                            else:
                                st.caption("No rooms yet.")
