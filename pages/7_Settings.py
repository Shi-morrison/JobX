"""JobX — Settings & Search"""

import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Settings — JobX", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings")

tab1, tab2, tab3 = st.tabs(["Resume", "Search", "Database"])

# ---------------------------------------------------------------------------
# Tab 1: Resume
# ---------------------------------------------------------------------------

with tab1:
    st.subheader("Base Resume")

    resume_path = Path("data/base_resume.docx")
    cache_path = Path("data/resume_parsed.json")

    if resume_path.exists():
        st.success(f"Resume found: `{resume_path}`")
        st.caption(f"Last modified: {Path(resume_path).stat().st_mtime:.0f}")
    else:
        st.error("No resume found at `data/base_resume.docx`")
        st.info("Upload your resume below, or place it manually at `data/base_resume.docx`.")

    uploaded = st.file_uploader("Upload new resume (.docx)", type=["docx"])
    if uploaded:
        Path("data").mkdir(exist_ok=True)
        resume_path.write_bytes(uploaded.read())
        st.success("Resume saved. Parse it below.")

    st.subheader("Parse Resume")
    if cache_path.exists():
        st.info("Resume cache exists. Re-parse to update after changing your resume.")
        import json
        try:
            parsed = json.loads(cache_path.read_text())
            pc1, pc2 = st.columns(2)
            pc1.metric("Name", parsed.get("personal", {}).get("name", "—"))
            pc2.metric("Skills found", len(parsed.get("skills", [])))
            with st.expander("View parsed skills"):
                st.write(", ".join(parsed.get("skills", [])))
            with st.expander("View parsed experience"):
                for exp in parsed.get("experience", []):
                    if isinstance(exp, dict):
                        st.markdown(f"**{exp.get('title', '—')}** @ {exp.get('company', '—')} ({exp.get('dates', '—')})")
        except Exception:
            pass
    else:
        st.caption("No cache yet.")

    if st.button("🔄 Parse / Re-parse Resume", type="primary"):
        if not resume_path.exists():
            st.error("No resume file found.")
        else:
            with st.spinner("Parsing resume with Claude..."):
                try:
                    from tools.llm import parse_resume
                    result = parse_resume(force=True)
                    st.success(f"Parsed: {result.get('personal', {}).get('name', 'Unknown')} — {len(result.get('skills', []))} skills found.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Parse failed: {e}")

# ---------------------------------------------------------------------------
# Tab 2: Search settings
# ---------------------------------------------------------------------------

def _update_env(key: str, value: str):
    """Update or add a key in the .env file."""
    env_path = Path(".env")
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n")


with tab2:
    st.subheader("Search Configuration")

    try:
        from config import settings

        cc1, cc2 = st.columns(2)
        new_comp_min = cc1.number_input(
            "Min Target Comp ($)",
            min_value=0, max_value=1000000,
            value=settings.target_comp_min,
            step=5000,
        )
        new_min_score = cc2.number_input(
            "Min Fit Score (1–10)",
            min_value=1, max_value=10,
            value=settings.min_fit_score,
        )

        if st.button("💾 Save", key="save_config"):
            _update_env("TARGET_COMP_MIN", str(new_comp_min))
            _update_env("MIN_FIT_SCORE", str(new_min_score))
            st.success("Saved to .env — restart the app to apply.")

        with st.expander("Other settings (edit .env directly)"):
            st.markdown(f"**Target Roles:** {', '.join(settings.target_roles)}")
            st.markdown(f"**Target Locations:** {', '.join(settings.target_locations)}")
            st.caption("To change roles or locations, edit `TARGET_ROLES` and `TARGET_LOCATIONS` in `.env` as JSON arrays.")

    except Exception as e:
        st.error(f"Could not load config: {e}")

    st.divider()
    st.subheader("Run Search")

    sc1, sc2, sc3, sc4 = st.columns(4)
    location = sc1.text_input("Location override", placeholder="remote / New York")
    level = sc2.selectbox("Seniority", ["", "junior", "mid", "senior", "staff"])
    results_per = sc3.number_input("Results per query", min_value=5, max_value=50, value=15)
    hours_back = sc4.number_input("Hours back", min_value=1, max_value=168, value=24)

    if st.button("🔍 Search for Jobs", type="primary"):
        with st.spinner("Scraping job listings..."):
            try:
                from tools.scraper import run_scraper
                run_scraper(
                    hours_back=int(hours_back),
                    location_override=location or None,
                    level=level or None,
                    results_per_query=int(results_per),
                )
                st.success("Search complete. Go to **Score** or check **Jobs**.")
            except Exception as e:
                st.error(f"Search failed: {e}")

    st.divider()
    st.subheader("Score Unscored Jobs")

    bc1, bc2 = st.columns([1, 1])
    score_limit = bc1.number_input("Max to score", min_value=1, max_value=100, value=10)
    score_recent = bc2.checkbox("Score most recent first")

    if st.button("🎯 Score Jobs", type="primary"):
        with st.spinner(f"Scoring up to {score_limit} jobs with Claude..."):
            try:
                from agents.scorer import run_scorer
                run_scorer(limit=int(score_limit), recent=score_recent)
                st.success("Scoring complete. Check the **Jobs** page.")
            except Exception as e:
                st.error(f"Scoring failed: {e}")

    st.divider()
    st.subheader("Backfill Missing Descriptions")
    desc_limit = st.number_input("Max jobs to backfill", min_value=1, max_value=100, value=20)
    if st.button("Fetch Descriptions"):
        with st.spinner("Fetching descriptions from LinkedIn..."):
            try:
                from tools.scraper import run_fetch_descriptions
                run_fetch_descriptions(limit=int(desc_limit))
                st.success("Done.")
            except Exception as e:
                st.error(f"Failed: {e}")

# ---------------------------------------------------------------------------
# Tab 3: Database
# ---------------------------------------------------------------------------

with tab3:
    st.subheader("Database Stats")

    @st.cache_data(ttl=30)
    def load_db_stats():
        from db.session import get_session
        from db.models import Job, Application, Contact, CompanyResearch, SalaryData, InterviewPrep
        with get_session() as db:
            return {
                "Jobs": db.query(Job).count(),
                "Applications": db.query(Application).count(),
                "Contacts": db.query(Contact).count(),
                "Company Research": db.query(CompanyResearch).count(),
                "Salary Records": db.query(SalaryData).count(),
                "Prep Sessions": db.query(InterviewPrep).count(),
            }

    try:
        stats = load_db_stats()
        cols = st.columns(len(stats))
        for col, (label, count) in zip(cols, stats.items()):
            col.metric(label, count)
    except Exception as e:
        st.error(f"Could not load DB stats: {e}")

    st.divider()
    db_path = Path("data/jobs.db")
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        st.caption(f"Database: `{db_path}` — {size_kb:.1f} KB")
        st.download_button(
            "⬇️ Download jobs.db backup",
            db_path.read_bytes(),
            file_name="jobs_backup.db",
            mime="application/octet-stream",
        )

    st.divider()
    st.subheader("API Keys Status")
    try:
        from config import settings
        keys = {
            "ANTHROPIC_API_KEY": bool(settings.anthropic_api_key),
            "SERPAPI_KEY": bool(settings.serpapi_key),
            "GMAIL_CLIENT_ID": bool(settings.gmail_client_id),
            "GMAIL_CLIENT_SECRET": bool(settings.gmail_client_secret),
        }
        for key, present in keys.items():
            icon = "✅" if present else "❌"
            st.markdown(f"{icon} `{key}`")
        if not Path("token.json").exists():
            st.caption("⚠️ `token.json` missing — run `python tools/gmail_auth.py` to enable Gmail send.")
    except Exception as e:
        st.error(str(e))
