"""JobX — Run Pipeline (Orchestrator)"""

import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Pipeline — JobX", page_icon="🚀", layout="wide")
st.title("🚀 Pipeline")
st.caption("Research → Tailor → Cover Letter → Prep → Salary — all in one run.")

# ---------------------------------------------------------------------------
# Job selector
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def load_scored_jobs():
    from db.session import get_session
    from db.models import Job
    with get_session() as db:
        jobs = db.query(Job).filter(
            Job.fit_score.isnot(None)
        ).order_by(Job.fit_score.desc()).all()
    return [(j.id, j.title, j.company, j.fit_score) for j in jobs]


try:
    job_options = load_scored_jobs()
except Exception as e:
    st.error(f"Could not load jobs: {e}")
    st.stop()

if not job_options:
    st.info("No scored jobs yet. Go to **Search** then **Score** first.")
    st.stop()

# Mark which jobs have a completed pipeline (tailored resume exists)
def _pipeline_done(job_id):
    return Path(f"data/resume_versions/resume_{job_id}.docx").exists()

pipeline_done_ids = {i for i, *_ in job_options if _pipeline_done(i)}

fc1, fc2 = st.columns([3, 1])
show_filter = fc2.selectbox("Show", ["all", "pipeline done", "pipeline pending"], key="pipe_filter")

filtered_options = [
    (i, t, c, s) for i, t, c, s in job_options
    if show_filter == "all"
    or (show_filter == "pipeline done" and i in pipeline_done_ids)
    or (show_filter == "pipeline pending" and i not in pipeline_done_ids)
]

if not filtered_options:
    st.info("No jobs match that filter.")
    st.stop()

job_labels = {
    f"{'✅' if i in pipeline_done_ids else '○'} {t} @ {c} (ID {i}) — {s}/10": i
    for i, t, c, s in filtered_options
}

# Pre-select from session state if navigated here from Jobs page
default_label = None
if "pipeline_job_id" in st.session_state:
    for label, jid in job_labels.items():
        if jid == st.session_state["pipeline_job_id"]:
            default_label = label
            break

selected_label = fc1.selectbox(
    "Select a job  (✅ = pipeline already run)",
    list(job_labels.keys()),
    index=list(job_labels.keys()).index(default_label) if default_label else 0,
)
job_id = job_labels[selected_label]

# Options
col1, col2 = st.columns(2)
level = col1.selectbox("Role level (for salary)", ["senior", "mid", "junior", "staff", "principal"])
force = col2.checkbox("Re-run all steps (ignore cache)")

# ---------------------------------------------------------------------------
# Current outputs
# ---------------------------------------------------------------------------

def _file_download(path: Path, label: str, mime: str):
    if path.exists():
        st.download_button(label, path.read_bytes(), file_name=path.name, mime=mime)
    else:
        st.caption(f"_{label} not generated yet_")


st.subheader("Current Outputs")
oc1, oc2 = st.columns(2)
with oc1:
    _file_download(Path(f"data/resume_versions/resume_{job_id}.docx"), "📄 Download Tailored Resume", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
with oc2:
    _file_download(Path(f"data/cover_letters/cover_letter_{job_id}.docx"), "✉️ Download Cover Letter", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

st.divider()

# ---------------------------------------------------------------------------
# Run pipeline
# ---------------------------------------------------------------------------

if st.button("▶️ Run Full Pipeline", type="primary", use_container_width=True):
    from db.session import get_session
    from db.models import Job

    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
    job_title = job.title if job else "?"
    job_company = job.company if job else "?"

    st.info(f"Running pipeline for **{job_title} @ {job_company}**... (progress shown in terminal)")

    steps = [
        ("🏢 Company Research", "research"),
        ("📄 Resume Tailor", "tailor"),
        ("✉️ Cover Letter", "cover_letter"),
        ("📚 Interview Prep", "prep"),
        ("💰 Salary Intel", "salary"),
    ]
    results = {}
    progress = st.progress(0)
    status_area = st.empty()

    for i, (label, key) in enumerate(steps):
        status_area.markdown(f"**{label}...**")
        try:
            if key == "research":
                from agents.company_research import research_company, get_cached_research
                cached = get_cached_research(job_company)
                if cached and not force:
                    results[key] = ("cached", cached)
                else:
                    data = research_company(job_company, force=force)
                    results[key] = ("done", data)

            elif key == "tailor":
                tailored = Path(f"data/resume_versions/resume_{job_id}.docx")
                if tailored.exists() and not force:
                    results[key] = ("cached", str(tailored))
                else:
                    from agents.resume_tailor import run_tailor
                    run_tailor(job_id=job_id)
                    results[key] = ("done", str(tailored))

            elif key == "cover_letter":
                cl = Path(f"data/cover_letters/cover_letter_{job_id}.docx")
                if cl.exists() and not force:
                    results[key] = ("cached", str(cl))
                else:
                    from agents.cover_letter import run_cover_letter
                    run_cover_letter(job_id=job_id)
                    results[key] = ("done", str(cl))

            elif key == "prep":
                from agents.interview_prep import run_prep
                run_prep(job_id=job_id, force=force)
                results[key] = ("done", None)

            elif key == "salary":
                from agents.salary_intel import fetch_salary_data
                salary = fetch_salary_data(job_company, level, force=force)
                results[key] = ("done" if salary.get("found") else "not found", salary)

        except Exception as e:
            results[key] = ("error", str(e))

        progress.progress((i + 1) / len(steps))

    status_area.empty()
    st.cache_data.clear()

    # Results summary
    st.subheader("Results")
    for label, key in steps:
        status, data = results.get(key, ("skipped", None))
        icon = "✅" if status in ("done", "cached") else "⚠️" if status == "not found" else "❌"
        tag = " _(cached)_" if status == "cached" else ""
        st.markdown(f"{icon} **{label}**{tag}")

    # Downloads
    st.subheader("Downloads")
    dc1, dc2 = st.columns(2)
    with dc1:
        _file_download(Path(f"data/resume_versions/resume_{job_id}.docx"), "📄 Tailored Resume", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    with dc2:
        _file_download(Path(f"data/cover_letters/cover_letter_{job_id}.docx"), "✉️ Cover Letter", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    # Salary display
    if "salary" in results:
        _, salary_data = results["salary"]
        if isinstance(salary_data, dict) and salary_data.get("found"):
            st.subheader("💰 Salary Intel")
            sc1, sc2, sc3 = st.columns(3)
            lo = salary_data.get("salary_min")
            hi = salary_data.get("salary_max")
            sc1.metric("Range Low", f"${lo:,}" if lo else "—")
            sc2.metric("Range High", f"${hi:,}" if hi else "—")
            sc3.metric("Matched Role", salary_data.get("matched_role", "—"))
            if salary_data.get("equity"):
                st.caption(f"Equity: {salary_data['equity']}")

    # Research display
    if "research" in results:
        _, research_data = results["research"]
        if isinstance(research_data, dict) and research_data.get("summary"):
            st.subheader("🏢 Company Summary")
            st.info(research_data["summary"])
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Glassdoor", f"{research_data.get('glassdoor_rating', '—')}/5" if research_data.get('glassdoor_rating') else "—")
            rc2.metric("Stage", research_data.get("funding_stage") or "—")
            rc3.metric("Employees", research_data.get("employee_count") or "—")

    st.success("Pipeline complete!")
    st.balloons()

    st.subheader("Next Steps")
    nc1, nc2, nc3, nc4 = st.columns(4)
    nc1.page_link("pages/4_Prep.py", label="📚 View Prep", icon="📚")
    nc2.page_link("pages/3_Research.py", label="🏢 View Research", icon="🏢")
    nc3.page_link("pages/5_Outreach.py", label="📨 Outreach", icon="📨")
    nc4.page_link("pages/1_Jobs.py", label="📋 Back to Jobs", icon="📋")

# ---------------------------------------------------------------------------
# Apply section
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Apply")

acol1, acol2 = st.columns(2)
if acol1.button("📝 Dry Run (fill form, no submit)", use_container_width=True):
    with st.spinner("Filling form via Playwright..."):
        try:
            from agents.autofill import run_apply
            run_apply(job_id=job_id, submit=False)
            st.success("Dry run complete. Check data/screenshots/ to review.")
        except Exception as e:
            st.error(f"Autofill failed: {e}")

if acol2.button("🚨 Submit Application", use_container_width=True, type="primary"):
    confirm = st.checkbox("I've reviewed the dry run screenshot and want to submit for real")
    if confirm:
        with st.spinner("Submitting application..."):
            try:
                from agents.autofill import run_apply
                run_apply(job_id=job_id, submit=True)
                st.success("Application submitted and logged.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Autofill failed: {e}")
    else:
        st.warning("Check the box above to confirm submission.")
