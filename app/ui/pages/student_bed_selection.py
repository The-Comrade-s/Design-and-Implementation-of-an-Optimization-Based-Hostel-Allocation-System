from __future__ import annotations

import streamlit as st

from app.core.database import get_session
from app.core.exceptions import HOSException
from app.models.hostel import AccommodationStatus, BedStatus
from app.services import allocation_service, bed_request_service, hostel_service, student_service
from app.utils.session import current_user_id


def _location(a) -> dict:
    return {
        "Hostel": a.hostel.name, "Block": a.block.name, "Floor": a.floor.name,
        "Room": a.room.room_number, "Bed": a.bed_space.bed_identifier,
    }


def render() -> None:
    st.header("Choose Your Hostel, Room & Bed Space")

    # Read everything into plain data while the session is open.
    with get_session() as session:
        student = student_service.get_student_by_user(session, current_user_id())
        if not student:
            st.warning("No student profile is linked to your account. Contact an administrator.")
            return
        student_pk, gender, academic_session = student.id, student.gender.value, student.academic_session
        name = student.full_name

        eligibility = student_service.check_student_eligibility(session, student_pk)
        elig_ok, elig_reason = eligibility.eligible, eligibility.reason

        current = bed_request_service.get_active_request(session, student_pk, academic_session)
        current_info = None
        if current:
            current_info = {"id": current.id, "status": current.status.value, "where": _location(current)}

        declined_info = None
        if not current:
            declined = bed_request_service.get_last_declined(session, student_pk, academic_session)
            if declined:
                declined_info = {"where": _location(declined), "reason": declined.release_reason}

        tree: dict = {}
        if not current and elig_ok:
            occupied = allocation_service.occupied_bed_ids(session, academic_session)
            for h in hostel_service.list_hostels(session):
                if h.status != AccommodationStatus.ACTIVE or h.category.value not in ("MIXED", gender):
                    continue
                for b in h.blocks:
                    if b.status != AccommodationStatus.ACTIVE:
                        continue
                    for f in b.floors:
                        if f.status != AccommodationStatus.ACTIVE:
                            continue
                        for r in f.rooms:
                            if r.status != AccommodationStatus.ACTIVE:
                                continue
                            beds = [(bd.bed_identifier, bd.id) for bd in r.bed_spaces
                                    if bd.status == BedStatus.AVAILABLE and bd.id not in occupied]
                            if not beds:
                                continue
                            room_label = f"Room {r.room_number} ({r.room_type.value.replace('_', ' ').title()}, {len(beds)} free)"
                            (tree.setdefault(f"{h.name} ({h.category.value.title()})", {})
                                 .setdefault(b.name, {})
                                 .setdefault(f"Floor {f.name}", {})[room_label]) = beds

    st.caption(f"{name} — {academic_session}")

    # ---- Already has a request / allocation ----
    if current_info:
        status = current_info["status"]
        if status == "PUBLISHED":
            st.success("You have been allocated this bed space.")
        elif status == "APPROVED":
            st.info("Your request has been approved and is awaiting publication.")
        else:
            st.info("Your request is awaiting review by the hostel administrator. "
                    "The bed is being held for you.")
        st.write(current_info["where"])
        if status in ("PROPOSED", "UNDER_REVIEW"):
            if st.button("Cancel this request"):
                try:
                    with get_session() as session:
                        bed_request_service.cancel_bed_request(session, current_info["id"], student_pk)
                    st.rerun()
                except HOSException as exc:
                    st.error(exc.message)
        return

    if declined_info:
        st.warning(f"Your previous request was declined: {declined_info['reason']}")
        st.caption("Previous choice: " + ", ".join(f"{k} {v}" for k, v in declined_info["where"].items()))

    if not elig_ok:
        st.error(f"You cannot request a bed yet: {elig_reason}")
        return

    if not tree:
        st.info("There are no free bed spaces available for you right now. Please check back later.")
        return

    # ---- Cascading selection ----
    st.write("Pick where you want to stay:")
    hostel_label = st.selectbox("Hostel", list(tree.keys()), key="sel_hostel")
    block_label = st.selectbox("Block", list(tree[hostel_label].keys()), key="sel_block")
    floor_label = st.selectbox("Floor", list(tree[hostel_label][block_label].keys()), key="sel_floor")
    rooms = tree[hostel_label][block_label][floor_label]
    room_label = st.selectbox("Room", list(rooms.keys()), key="sel_room")
    beds = {identifier: bed_id for identifier, bed_id in rooms[room_label]}
    bed_label = st.selectbox("Bed space", list(beds.keys()), key="sel_bed")

    st.info(f"You selected: {hostel_label} → {block_label} → {floor_label} → {room_label} → Bed {bed_label}")
    st.caption("The administrator will review your request and allocate the bed if you qualify.")

    if st.button("Request this bed", type="primary"):
        try:
            with get_session() as session:
                bed_request_service.create_bed_request(
                    session, student_id=student_pk, bed_id=beds[bed_label], actor_id=current_user_id(),
                )
            st.rerun()
        except HOSException as exc:
            st.error(exc.message)
