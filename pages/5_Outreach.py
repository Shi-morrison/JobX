"""JobX — Outreach & Contacts"""

import streamlit as st

st.set_page_config(page_title="Outreach — JobX", page_icon="📨", layout="wide")
st.title("📨 Outreach")

tab1, tab2, tab3 = st.tabs(["Generate Messages", "Follow-Ups Due", "All Contacts"])

# ---------------------------------------------------------------------------
# Tab 1: Generate outreach messages
# ---------------------------------------------------------------------------

with tab1:
    st.subheader("Generate Outreach Messages")

    @st.cache_data(ttl=30)
    def load_jobs_with_contacts():
        from db.session import get_session
        from db.models import Job, Contact, OutreachSequence
        with get_session() as db:
            jobs = db.query(Job).filter(Job.fit_score.isnot(None)).order_by(Job.fit_score.desc()).all()
            contacts = db.query(Contact).all()
            sequences = db.query(OutreachSequence).all()
        contact_job_ids = {c.job_id for c in contacts}
        messaged_job_ids = {s.contact_id for s in sequences}
        return [(j.id, j.title, j.company) for j in jobs], contact_job_ids, messaged_job_ids

    try:
        job_opts, contact_job_ids, messaged_contact_ids = load_jobs_with_contacts()
    except Exception as e:
        st.error(str(e))
        st.stop()

    of1, of2 = st.columns([3, 1])
    show_filter = of2.selectbox("Show", ["all", "has contacts", "no contacts yet"], key="outreach_filter")

    filtered_opts = [
        (i, t, c) for i, t, c in job_opts
        if show_filter == "all"
        or (show_filter == "has contacts" and i in contact_job_ids)
        or (show_filter == "no contacts yet" and i not in contact_job_ids)
    ]

    if not filtered_opts:
        st.info("No jobs match that filter.")
        st.stop()

    job_labels = {f"{'👤' if i in contact_job_ids else '○'} {t} @ {c} (ID {i})": i for i, t, c in filtered_opts}
    selected = of1.selectbox("Select job  (👤 = contacts exist)", list(job_labels.keys()) if job_labels else ["No jobs"])
    job_id = job_labels.get(selected)

    if job_id:
        # Show existing contacts
        from db.session import get_session
        from db.models import Contact
        with get_session() as db:
            contacts = db.query(Contact).filter(Contact.job_id == job_id).all()

        if contacts:
            st.caption(f"{len(contacts)} contact(s) saved for this job.")
            for c in contacts:
                st.markdown(f"• **{c.name or '—'}** — {c.title or '—'} @ {c.company or '—'}")
                if c.linkedin_url:
                    st.caption(f"  LinkedIn: {c.linkedin_url}")
        else:
            st.caption("No contacts yet for this job.")
            st.info("Find contacts first:")
            st.code(f"python main.py referrals --job-id {job_id}    # from LinkedIn CSV\npython main.py find-contacts --job-id {job_id}  # SerpAPI search")

        if contacts:
            show_msgs = st.checkbox("Show generated messages")
            if st.button("✉️ Generate Messages", type="primary"):
                with st.spinner("Writing personalized messages with Claude..."):
                    try:
                        from agents.outreach import run_outreach
                        run_outreach(job_id=job_id, send=False, messages=False)
                        st.success("Messages generated and saved.")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Failed: {e}")

            # Show saved message content
            from db.models import OutreachSequence
            with get_session() as db:
                seqs = db.query(OutreachSequence).filter(
                    OutreachSequence.contact_id.in_([c.id for c in contacts])
                ).all()

            if seqs and show_msgs:
                contact_map = {c.id: c for c in contacts}
                for seq in seqs:
                    contact = contact_map.get(seq.contact_id)
                    name = contact.name if contact else "—"
                    with st.expander(f"{seq.message_type.title()} — {name}"):
                        st.text(seq.content or "No content yet")
                        if seq.status == "pending":
                            if st.button(f"Mark as sent", key=f"sent_{seq.id}"):
                                from agents.outreach import mark_sent
                                mark_sent(seq.id)
                                st.success("Marked as sent.")
                                st.rerun()

# ---------------------------------------------------------------------------
# Tab 2: Follow-ups due
# ---------------------------------------------------------------------------

with tab2:
    st.subheader("Follow-Ups Due")

    try:
        from agents.outreach import get_due_followups, auto_ghost_stale
        ghosted = auto_ghost_stale()
        if ghosted:
            st.caption(f"Auto-ghosted {ghosted} stale sequence(s).")
        due = get_due_followups()
    except Exception as e:
        st.error(str(e))
        due = []

    if not due:
        st.success("No follow-ups due. 🎉")
    else:
        st.warning(f"{len(due)} follow-up(s) need attention.")
        for d in due:
            color = "🔴" if d["ghosted"] else "🟡"
            with st.expander(f"{color} {d['contact_name']} @ {d['company']} — {d['days_since']} days ago"):
                st.markdown(f"**Job:** {d['job_title']}")
                st.markdown(f"**Type:** {d['message_type']}")
                st.markdown(f"**Status:** {d['status']}")

                bc1, bc2 = st.columns(2)
                if bc1.button("Mark Responded", key=f"resp_{d['seq_id']}"):
                    from agents.outreach import mark_responded
                    mark_responded(d["seq_id"])
                    st.success("Marked as responded.")
                    st.rerun()

# ---------------------------------------------------------------------------
# Tab 3: All contacts
# ---------------------------------------------------------------------------

with tab3:
    st.subheader("All Saved Contacts")

    @st.cache_data(ttl=30)
    def load_all_contacts():
        from db.session import get_session
        from db.models import Contact, Job
        with get_session() as db:
            contacts = db.query(Contact).all()
            job_map = {j.id: j for j in db.query(Job).all()}
        return [
            {
                "Name": c.name or "—",
                "Title": c.title or "—",
                "Company": c.company or "—",
                "Job": job_map[c.job_id].title if c.job_id in job_map else "—",
                "LinkedIn": c.linkedin_url or "—",
                "Email": c.email or "—",
            }
            for c in contacts
        ]

    try:
        contact_rows = load_all_contacts()
        if contact_rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(contact_rows), width="stretch")
        else:
            st.caption("No contacts saved yet.")
    except Exception as e:
        st.error(str(e))
