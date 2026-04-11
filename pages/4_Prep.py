"""JobX — Interview Prep"""

import streamlit as st

st.set_page_config(page_title="Prep — JobX", page_icon="📚", layout="wide")
st.title("📚 Interview Prep")

# ---------------------------------------------------------------------------
# Job selector
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def load_jobs_with_prep():
    from db.session import get_session
    from db.models import Job, InterviewPrep
    with get_session() as db:
        jobs = db.query(Job).filter(Job.fit_score.isnot(None)).order_by(Job.fit_score.desc()).all()
        prep_ids = {p.job_id for p in db.query(InterviewPrep).all()}
    return [(j.id, j.title, j.company, j.fit_score) for j in jobs], prep_ids


try:
    job_options, prep_ids = load_jobs_with_prep()
except Exception as e:
    st.error(f"Could not load jobs: {e}")
    st.stop()

if not job_options:
    st.info("No scored jobs. Score a job first.")
    st.stop()

job_labels = {
    f"{'✅' if i in prep_ids else '○'} {t} @ {c} (ID {i})": i
    for i, t, c, s in job_options
}

default_label = None
if "prep_job_id" in st.session_state:
    for label, jid in job_labels.items():
        if jid == st.session_state["prep_job_id"]:
            default_label = label
            break

selected_label = st.selectbox(
    "Select job (✅ = prep already generated)",
    list(job_labels.keys()),
    index=list(job_labels.keys()).index(default_label) if default_label else 0,
)
job_id = job_labels[selected_label]

# ---------------------------------------------------------------------------
# Generate prep
# ---------------------------------------------------------------------------

col1, col2 = st.columns([1, 1])
force = col2.checkbox("Regenerate (ignore cache)")
if col1.button("▶️ Generate Prep", type="primary", disabled=(job_id in prep_ids and not force)):
    st.info("Generating interview prep... this takes 2–5 minutes. Progress shown in terminal.")
    with st.spinner("Running 7-step prep pipeline..."):
        try:
            from agents.interview_prep import run_prep
            run_prep(job_id=job_id, force=force)
            st.cache_data.clear()
            st.success("Prep generated!")
            st.rerun()
        except Exception as e:
            st.error(f"Prep generation failed: {e}")

if job_id not in prep_ids:
    st.caption("Prep not yet generated for this job. Click Generate Prep above.")
    st.stop()

# ---------------------------------------------------------------------------
# Load and display prep
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def load_prep(jid):
    from db.session import get_session
    from db.models import InterviewPrep, Job
    with get_session() as db:
        prep = db.query(InterviewPrep).filter(InterviewPrep.job_id == jid).first()
        job = db.query(Job).filter(Job.id == jid).first()
    return prep, job


prep, job = load_prep(job_id)
if not prep:
    st.warning("Prep record not found.")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["💻 Technical", "🤝 Behavioral", "🏢 Company", "📅 Study Plan", "🎭 Mock Interview"])

# ---------------------------------------------------------------------------
# Technical tab
# ---------------------------------------------------------------------------

with tab1:
    tech = prep.technical_questions or {}
    if not tech:
        st.caption("No technical questions generated.")
    else:
        for category, questions in tech.items():
            st.subheader(category)
            if isinstance(questions, list):
                for q in questions:
                    if isinstance(q, dict):
                        with st.expander(q.get("question", str(q))):
                            if q.get("difficulty"):
                                st.caption(f"Difficulty: {q['difficulty']}")
                            if q.get("hint"):
                                st.markdown(f"**Hint:** {q['hint']}")
                            if q.get("url"):
                                st.markdown(f"[LeetCode ↗]({q['url']})")
                    else:
                        st.markdown(f"• {q}")

# ---------------------------------------------------------------------------
# Behavioral tab
# ---------------------------------------------------------------------------

with tab2:
    behavioral = prep.behavioral_questions or []
    if not behavioral:
        st.caption("No behavioral questions generated.")
    else:
        for q in behavioral:
            if isinstance(q, dict):
                with st.expander(q.get("question", str(q))):
                    if q.get("star_framework"):
                        st.markdown("**STAR Framework:**")
                        sf = q["star_framework"]
                        if isinstance(sf, dict):
                            for k, v in sf.items():
                                st.markdown(f"- **{k.title()}:** {v}")
                        else:
                            st.markdown(str(sf))
            else:
                st.markdown(f"• {q}")

# ---------------------------------------------------------------------------
# Company tab
# ---------------------------------------------------------------------------

with tab3:
    company_q = prep.company_questions or {}
    why_us = company_q.get("why_us_talking_points", []) if isinstance(company_q, dict) else []
    questions = company_q.get("company_questions", []) if isinstance(company_q, dict) else []
    comp_data = company_q.get("compensation") if isinstance(company_q, dict) else None

    if why_us:
        st.subheader("Why Us — Talking Points")
        for pt in why_us:
            st.markdown(f"✦ {pt}")

    if questions:
        st.subheader("Questions to Ask the Interviewer")
        for q in questions:
            if isinstance(q, dict):
                with st.expander(q.get("question", str(q))):
                    st.caption(q.get("talking_point", ""))
            else:
                st.markdown(f"• {q}")

    if comp_data:
        st.subheader("💰 Compensation Context")
        if isinstance(comp_data, dict):
            st.metric("Median Total Comp", comp_data.get("median_total_comp", "—"))

# ---------------------------------------------------------------------------
# Study plan tab
# ---------------------------------------------------------------------------

with tab4:
    study = prep.study_plan or []
    if not study:
        st.caption("No study plan generated.")
    else:
        for item in study:
            if isinstance(item, dict):
                hours = item.get("hours", "")
                topic = item.get("topic", str(item))
                col_a, col_b = st.columns([4, 1])
                col_a.markdown(f"**{topic}**")
                if hours:
                    col_b.caption(f"{hours}h")
                if item.get("resources"):
                    for r in item["resources"]:
                        st.caption(f"  → {r}")
            else:
                st.markdown(f"• {item}")

# ---------------------------------------------------------------------------
# Mock interview tab
# ---------------------------------------------------------------------------

with tab5:
    st.subheader("Mock Interview")
    st.caption("Claude acts as the interviewer. Answer each question, get scored and critiqued.")

    # Collect all questions for the session
    if "mock_questions" not in st.session_state or st.session_state.get("mock_job_id") != job_id:
        all_qs = []
        tech = prep.technical_questions or {}
        for cat, qs in tech.items():
            if cat == "Glassdoor":
                continue
            for q in (qs or [])[:2]:
                if isinstance(q, dict):
                    all_qs.append({"type": "technical", "question": q.get("question", ""), "category": cat})
        behavioral = prep.behavioral_questions or []
        for q in behavioral[:3]:
            if isinstance(q, dict):
                all_qs.append({"type": "behavioral", "question": q.get("question", "")})
        company_q = prep.company_questions or {}
        for q in (company_q.get("company_questions", []) if isinstance(company_q, dict) else [])[:1]:
            if isinstance(q, dict):
                all_qs.append({"type": "company", "question": q.get("question", "")})

        st.session_state["mock_questions"] = all_qs
        st.session_state["mock_job_id"] = job_id
        st.session_state["mock_idx"] = 0
        st.session_state["mock_results"] = []

    questions = st.session_state["mock_questions"]
    idx = st.session_state.get("mock_idx", 0)
    results = st.session_state.get("mock_results", [])

    if not questions:
        st.caption("No questions available for mock session.")
    elif idx >= len(questions):
        st.success(f"Session complete! Answered {len(results)} question(s).")
        if results:
            avg = sum(r.get("score", 5) for r in results) / len(results)
            st.metric("Average Score", f"{avg:.1f}/10")
            for r in results:
                with st.expander(r["question"][:80]):
                    st.markdown(f"**Your answer:** {r['answer']}")
                    st.markdown(f"**Score:** {r.get('score', '—')}/10")
                    st.markdown(f"**Feedback:** {r.get('critique', '—')}")
                    if r.get("stronger_answer"):
                        st.markdown(f"**Stronger answer:** {r['stronger_answer']}")
        if st.button("Restart Session"):
            st.session_state["mock_idx"] = 0
            st.session_state["mock_results"] = []
            st.rerun()
    else:
        current_q = questions[idx]
        st.progress((idx) / len(questions))
        st.caption(f"Question {idx + 1} of {len(questions)} — {current_q['type'].title()}")
        st.markdown(f"### {current_q['question']}")

        answer = st.text_area("Your answer", height=150, key=f"mock_answer_{idx}")
        mc1, mc2 = st.columns(2)

        if mc1.button("Submit Answer", type="primary"):
            if not answer.strip():
                st.warning("Write an answer first.")
            else:
                with st.spinner("Scoring your answer..."):
                    try:
                        from tools.llm import ClaudeClient
                        client = ClaudeClient()
                        eval_result = client.chat_json(
                            messages=[{"role": "user", "content": (
                                f"Score this interview answer 1-10.\n\n"
                                f"Question: {current_q['question']}\n"
                                f"Answer: {answer}\n\n"
                                'Return JSON: {"score": <int>, "critique": "<2 sentences>", "stronger_answer": "<1 paragraph>"}'
                            )}],
                            max_tokens=512,
                        )
                        st.session_state["mock_results"].append({
                            "question": current_q["question"],
                            "answer": answer,
                            **eval_result,
                        })
                        sc = eval_result.get("score", 5)
                        color = "🟢" if sc >= 7 else "🟡" if sc >= 5 else "🔴"
                        st.markdown(f"{color} **Score: {sc}/10**")
                        st.markdown(f"**Feedback:** {eval_result.get('critique', '')}")
                        with st.expander("See stronger answer"):
                            st.markdown(eval_result.get("stronger_answer", ""))
                        st.session_state["mock_idx"] = idx + 1
                    except Exception as e:
                        st.error(f"Scoring failed: {e}")

        if mc2.button("Skip"):
            st.session_state["mock_idx"] = idx + 1
            st.rerun()
