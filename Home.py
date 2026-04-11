"""JobX — Home / Daily Digest"""

import streamlit as st
from datetime import datetime, timedelta

st.set_page_config(
    page_title="JobX",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("💼 JobX")
st.caption(f"Daily Digest — {datetime.now().strftime('%A, %B %d %Y')}")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_digest():
    from db.session import get_session
    from db.models import Job, OutreachSequence, InterviewPrep
    from agents.hiring_signals import get_surge_companies

    with get_session() as db:
        jobs = db.query(Job).all()
        seqs = db.query(OutreachSequence).all()
        prep = db.query(InterviewPrep).order_by(InterviewPrep.created_at.desc()).first()

    cutoff = datetime.utcnow() - timedelta(hours=24)
    new_jobs = [j for j in jobs if j.fit_score and j.created_at and j.created_at >= cutoff]
    new_jobs.sort(key=lambda j: j.fit_score, reverse=True)

    due_count = sum(
        1 for s in seqs
        if s.follow_up_due and s.follow_up_due <= datetime.utcnow()
        and not s.response_received
        and s.status in ("sent", "followed_up")
    )

    surges = get_surge_companies(days=7, min_jobs=3)

    study_items = []
    if prep and prep.study_plan:
        for item in (prep.study_plan or [])[:5]:
            if isinstance(item, dict) and item.get("topic"):
                study_items.append(item["topic"])

    pipeline = {
        "total": len(jobs),
        "scored": sum(1 for j in jobs if j.fit_score),
        "applied": sum(1 for j in jobs if j.status == "applied"),
        "interviewing": sum(1 for j in jobs if j.status == "interviewing"),
        "offer": sum(1 for j in jobs if j.status == "offer"),
        "avg_score": round(
            sum(j.fit_score for j in jobs if j.fit_score) / max(sum(1 for j in jobs if j.fit_score), 1), 1
        ),
    }

    return pipeline, new_jobs[:8], due_count, surges[:5], study_items


try:
    pipeline, new_jobs, due_count, surges, study_items = load_digest()
except Exception as e:
    st.error(f"Could not load data: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Pipeline metrics
# ---------------------------------------------------------------------------

st.subheader("Pipeline")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Jobs", pipeline["total"])
c2.metric("Scored", pipeline["scored"])
c3.metric("Applied", pipeline["applied"])
c4.metric("Interviewing", pipeline["interviewing"])
c5.metric("Offers", pipeline["offer"])

st.divider()

# ---------------------------------------------------------------------------
# Two-column layout: new jobs + action items
# ---------------------------------------------------------------------------

left, right = st.columns([3, 2])

with left:
    st.subheader("🆕 New Scored Jobs (last 24h)")
    if new_jobs:
        for j in new_jobs:
            score_color = "🟢" if j.fit_score >= 7 else "🟡" if j.fit_score >= 5 else "🔴"
            st.markdown(
                f"{score_color} **{j.fit_score}/10** — {j.title} @ **{j.company}**  "
                f"<span style='color:gray;font-size:0.85em'>ID {j.id}</span>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No new scored jobs in the last 24h.")
        st.caption("→ Go to **Search** then **Score** to pull fresh listings.")

with right:
    st.subheader("📋 Action Items")

    # Follow-ups
    if due_count > 0:
        st.warning(f"**{due_count}** follow-up(s) due today → Outreach page")
    else:
        st.success("No follow-ups due today.")

    # Surges
    if surges:
        st.subheader("⚡ Hiring Surges")
        for s in surges:
            st.markdown(f"**{s['company']}** — {s['job_count']} postings in 7 days")
    else:
        st.caption("No hiring surges detected.")

    # Study plan
    if study_items:
        st.subheader("📚 Study Plan")
        for item in study_items:
            st.markdown(f"• {item}")
    else:
        st.caption("No study plan yet — run Prep for a job.")

st.divider()
st.caption("Use the sidebar to navigate. Run `streamlit run Home.py` to restart.")
