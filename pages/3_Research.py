"""JobX — Company Research"""

import streamlit as st

st.set_page_config(page_title="Research — JobX", page_icon="🏢", layout="wide")
st.title("🏢 Company Research")
st.caption("Funding stage · Glassdoor rating · Tech stack · News · Layoff history")

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def load_jobs_for_research():
    from db.session import get_session
    from db.models import Job, CompanyResearch
    with get_session() as db:
        jobs = db.query(Job).filter(Job.fit_score.isnot(None)).order_by(Job.fit_score.desc()).all()
        researched = {r.company_name.lower() for r in db.query(CompanyResearch).all()}
    return [(j.id, j.title, j.company, j.fit_score) for j in jobs], researched


rf1, rf2 = st.columns([3, 1])

try:
    job_opts, researched_companies = load_jobs_for_research()
    show_filter = rf2.selectbox("Show", ["all", "researched", "not researched"], key="research_filter")
    filtered_jobs = [
        (i, t, c, s) for i, t, c, s in job_opts
        if show_filter == "all"
        or (show_filter == "researched" and c.lower() in researched_companies)
        or (show_filter == "not researched" and c.lower() not in researched_companies)
    ]
    if filtered_jobs:
        job_labels = {
            f"{'✅' if c.lower() in researched_companies else '○'} {t} @ {c} (ID {i})": c
            for i, t, c, s in filtered_jobs
        }
        chosen = rf1.selectbox("Quick-select from your jobs  (✅ = already researched)", ["— type manually below —"] + list(job_labels.keys()))
        preselect = job_labels.get(chosen, "") if chosen != "— type manually below —" else ""
    else:
        rf1.caption("No jobs match that filter.")
        preselect = ""
except Exception:
    preselect = ""

default_company = preselect or st.session_state.get("research_company", "")
company = st.text_input("Company name", value=default_company, placeholder="Stripe, Google, Robinhood...")
force = st.checkbox("Re-research (ignore cache)")

col1, col2 = st.columns([1, 4])
run_btn = col1.button("🔍 Research", type="primary")

# ---------------------------------------------------------------------------
# Show cached research for all companies
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_all_research():
    from db.session import get_session
    from db.models import CompanyResearch
    with get_session() as db:
        return db.query(CompanyResearch).order_by(CompanyResearch.created_at.desc()).all()


existing = load_all_research()
if existing and not run_btn:
    st.subheader("Cached Research")
    names = [r.company_name for r in existing]
    selected = st.selectbox("View cached company", ["— select —"] + names)

    if selected != "— select —":
        record = next((r for r in existing if r.company_name == selected), None)
        if record:
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("Glassdoor", f"{record.glassdoor_rating}/5" if record.glassdoor_rating else "—")
            rc2.metric("Stage", record.funding_stage or "—")
            rc3.metric("Employees", record.employee_count or "—")
            rc4.metric("Industry", record.industry or "—")

            if record.summary:
                st.info(record.summary)

            if record.tech_stack:
                st.subheader("Tech Stack")
                st.write(", ".join(record.tech_stack[:20]))

            if record.recent_news:
                st.subheader("Recent News")
                for n in record.recent_news[:5]:
                    st.markdown(f"• [{n.get('title', '—')}]({n.get('url', '#')})  \n  {n.get('snippet', '')}")

            if record.layoff_history:
                st.subheader("⚠️ Layoff Signals")
                for l in record.layoff_history:
                    st.warning(f"{l.get('title', '—')} — {l.get('snippet', '')}")

# ---------------------------------------------------------------------------
# Run research
# ---------------------------------------------------------------------------

if run_btn:
    if not company.strip():
        st.warning("Enter a company name.")
        st.stop()

    st.info(f"Researching **{company}**... this may take 30–60 seconds.")

    with st.spinner("Fetching data from levels.fyi, Glassdoor, StackShare, and SerpAPI..."):
        try:
            from agents.company_research import research_company
            result = research_company(company.strip(), force=force)
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Research failed: {e}")
            st.stop()

    st.subheader(f"Results: {company}")

    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric("Glassdoor", f"{result.get('glassdoor_rating', '—')}/5" if result.get('glassdoor_rating') else "—")
    rc2.metric("Stage", result.get("funding_stage") or "—")
    rc3.metric("Employees", result.get("employee_count") or "—")
    rc4.metric("Industry", result.get("industry") or "—")

    if result.get("summary"):
        st.info(result["summary"])

    signals = result.get("signals", {})
    if signals:
        sc1, sc2, sc3 = st.columns(3)
        sc1.markdown(f"**Growth stage:** {signals.get('growth_stage', '—')}")
        sc2.markdown(f"**Stability:** {signals.get('stability_flag', '—')}")
        sc3.markdown(f"**Tech rep:** {signals.get('tech_reputation', '—')}")

    if result.get("tech_stack"):
        st.subheader("Tech Stack")
        st.write(", ".join(result["tech_stack"][:20]))

    if result.get("recent_news"):
        st.subheader("Recent News")
        for n in result["recent_news"][:5]:
            st.markdown(f"• [{n.get('title', '—')}]({n.get('url', '#')})  \n  {n.get('snippet', '')}")

    if result.get("layoff_history"):
        st.subheader("⚠️ Layoff Signals")
        for l in result["layoff_history"]:
            st.warning(f"{l.get('title', '—')} — {l.get('snippet', '')}")

    st.success("Research cached. Will be used automatically by cover letter and interview prep.")

# ---------------------------------------------------------------------------
# Salary lookup
# ---------------------------------------------------------------------------

st.divider()
st.subheader("💰 Salary Lookup")

sc1, sc2, sc3 = st.columns([2, 1, 1])
sal_company = sc1.text_input("Company", value=company, key="sal_company")
sal_level = sc2.selectbox("Level", ["senior", "mid", "junior", "staff", "principal"])
if sc3.button("Look up salary", use_container_width=True):
    if not sal_company.strip():
        st.warning("Enter a company name.")
    else:
        with st.spinner("Fetching from levels.fyi..."):
            try:
                from agents.salary_intel import fetch_salary_data
                sal = fetch_salary_data(sal_company.strip(), sal_level)
            except Exception as e:
                st.error(f"Salary lookup failed: {e}")
                sal = {}

        if sal.get("found"):
            mc1, mc2, mc3 = st.columns(3)
            lo, hi = sal.get("salary_min"), sal.get("salary_max")
            mc1.metric("Low", f"${lo:,}" if lo else "—")
            mc2.metric("High", f"${hi:,}" if hi else "—")
            mc3.metric("Based on", sal.get("matched_role", "—"))
            if sal.get("equity"):
                st.caption(f"Equity: {sal['equity']}")
            if sal.get("notes"):
                st.caption(sal["notes"])

            if sal.get("all_levels"):
                with st.expander("All role levels"):
                    for fam in sal["all_levels"]:
                        st.markdown(f"• **{fam['role']}**: {fam['median']}")
        else:
            st.warning(f"No salary data found for {sal_company} on levels.fyi.")
