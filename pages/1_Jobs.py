"""JobX — Job Browser"""

import streamlit as st

st.set_page_config(page_title="Jobs — JobX", page_icon="📋", layout="wide")
st.title("📋 Jobs")

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
search_kw = col1.text_input("Search", placeholder="company or title...")
min_score = col2.slider("Min fit score", 1, 10, 1)
status_filter = col3.selectbox("Status", ["scored", "unscored", "applied", "all"])
sort_by = col4.selectbox("Sort by", ["fit score", "date posted"])
limit = col5.selectbox("Show", [25, 50, 100], index=0)

# ---------------------------------------------------------------------------
# Load jobs
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def load_jobs(search, min_sc, status, sort, lim):
    from db.session import get_session
    from db.models import Job
    from agents.hiring_signals import get_surge_companies_set

    surge_set = get_surge_companies_set()

    with get_session() as db:
        query = db.query(Job)

        if status == "scored":
            query = query.filter(Job.fit_score.isnot(None), Job.status != "applied")
        elif status == "unscored":
            query = query.filter(Job.fit_score.is_(None))
        elif status == "applied":
            query = query.filter(Job.status == "applied")

        if min_sc > 1:
            query = query.filter(Job.fit_score >= min_sc)

        if search:
            kw = f"%{search}%"
            from sqlalchemy import or_
            query = query.filter(or_(Job.title.ilike(kw), Job.company.ilike(kw)))

        if sort == "date posted":
            query = query.order_by(Job.posted_date.desc().nulls_last())
        else:
            query = query.order_by(Job.fit_score.desc().nulls_last())

        jobs = query.limit(lim).all()

    return jobs, surge_set


try:
    jobs, surge_set = load_jobs(search_kw, min_score, status_filter, sort_by, limit)
except Exception as e:
    st.error(f"Could not load jobs: {e}")
    st.stop()

st.caption(f"{len(jobs)} job(s) shown")

if not jobs:
    st.info("No jobs found. Try **Search** to scrape new listings.")
    st.stop()

# ---------------------------------------------------------------------------
# Job list
# ---------------------------------------------------------------------------

for job in jobs:
    score_icon = "🟢" if (job.fit_score or 0) >= 7 else "🟡" if (job.fit_score or 0) >= 5 else "🔴"
    surge_icon = " ⚡" if job.company in surge_set else ""
    score_str = f"{job.fit_score}/10" if job.fit_score else "unscored"
    posted = job.posted_date.strftime("%b %d") if job.posted_date else "—"
    has_desc = bool(job.description and job.description.strip() not in ("", "nan"))

    label = f"{score_icon} **{score_str}** — {job.title} @ **{job.company}**{surge_icon}  `ID {job.id}` · {posted}"

    with st.expander(label):
        dc1, dc2, dc3 = st.columns(3)
        dc1.markdown(f"**Fit Score:** {score_str}")
        dc2.markdown(f"**ATS:** {f'{job.ats_score:.0f}%' if job.ats_score else '—'}")
        dc3.markdown(f"**Status:** {job.status or '—'}")

        if job.url:
            st.markdown(f"[Open job posting ↗]({job.url})")

        gaps = job.gap_analysis or {}

        if gaps.get("fit_reasoning"):
            st.markdown("**Fit Reasoning:**")
            st.caption(gaps["fit_reasoning"])

        gcol1, gcol2 = st.columns(2)
        if gaps.get("hard_gaps"):
            with gcol1:
                st.markdown("**🔴 Hard Gaps:**")
                for g in gaps["hard_gaps"]:
                    st.markdown(f"• {g}")
        if gaps.get("soft_gaps"):
            with gcol2:
                st.markdown("**🟡 Soft Gaps:**")
                for g in gaps["soft_gaps"]:
                    st.markdown(f"• {g}")

        if gaps.get("reframe_suggestions"):
            st.markdown("**💡 Reframe Suggestions:**")
            for s in gaps["reframe_suggestions"]:
                st.markdown(f"- **{s['gap']}** → {s['suggestion']}")

        if has_desc:
            with st.expander("Job description preview"):
                st.caption(job.description[:800] + ("..." if len(job.description or "") > 800 else ""))
        else:
            st.caption("⚠️ No job description — fetch-descriptions required before scoring.")

        st.divider()
        ac1, ac2, ac3, ac4 = st.columns(4)

        if ac1.button("🚀 Run Pipeline", key=f"pipe_{job.id}"):
            st.session_state["pipeline_job_id"] = job.id
            st.switch_page("pages/2_Pipeline.py")

        if ac2.button("🏢 Research", key=f"research_{job.id}"):
            st.session_state["research_company"] = job.company
            st.switch_page("pages/3_Research.py")

        if ac3.button("📚 Prep", key=f"prep_{job.id}"):
            st.session_state["prep_job_id"] = job.id
            st.switch_page("pages/4_Prep.py")

        if job.status != "applied":
            if ac4.button("✅ Mark Applied", key=f"applied_{job.id}"):
                from db.session import get_session
                from db.models import Job as JobModel
                with get_session() as db:
                    j = db.query(JobModel).filter(JobModel.id == job.id).first()
                    if j:
                        j.status = "applied"
                st.cache_data.clear()
                st.success(f"Marked job {job.id} as applied.")
                st.rerun()
