"""JobX — Analytics"""

import streamlit as st

st.set_page_config(page_title="Analytics — JobX", page_icon="📊", layout="wide")
st.title("📊 Analytics")

@st.cache_data(ttl=60)
def load_all_analytics():
    from agents.analytics import compute_pipeline_stats, compute_outreach_stats, compute_top_segments
    return (
        compute_pipeline_stats(),
        compute_outreach_stats(),
        compute_top_segments(),
    )


try:
    pipeline, outreach, segments = load_all_analytics()
except Exception as e:
    st.error(f"Could not load analytics: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Pipeline metrics
# ---------------------------------------------------------------------------

st.subheader("Application Pipeline")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total in DB", pipeline["total_jobs_in_db"])
c2.metric("Scored", pipeline["scored"])
c3.metric("Applied", pipeline["applied"])
c4.metric("Avg Fit Score", f"{pipeline['avg_fit_score']}/10")
outcomes = pipeline.get("outcome_stages", {})
c5.metric("Interviews", sum(outcomes.values()))

# Outcome breakdown
if outcomes:
    st.subheader("Interview Stage Breakdown")
    import pandas as pd
    outcome_df = pd.DataFrame(
        [{"Stage": k.replace("_", " ").title(), "Count": v} for k, v in outcomes.items()]
    )
    st.bar_chart(outcome_df.set_index("Stage"))

st.divider()

# ---------------------------------------------------------------------------
# Outreach metrics
# ---------------------------------------------------------------------------

st.subheader("Outreach")
oc1, oc2, oc3, oc4 = st.columns(4)
oc1.metric("Sequences", outreach["total_sequences"])
oc2.metric("Sent", outreach["sent"])
oc3.metric("Responded", outreach["responded"])
rate = outreach["response_rate_pct"]
rate_delta = "good" if rate >= 20 else "low"
oc4.metric("Response Rate", f"{rate}%", delta=rate_delta)

st.divider()

# ---------------------------------------------------------------------------
# Segments chart
# ---------------------------------------------------------------------------

st.subheader("Outcomes by Fit Score Range")
try:
    import pandas as pd
    seg_df = pd.DataFrame([
        {
            "Fit Range": s["segment"],
            "Total": s["total"],
            "Applied": s["applied"],
            "Interviewed": s["interviewed"],
        }
        for s in segments
    ])
    st.dataframe(seg_df, width="stretch", hide_index=True)
    if seg_df["Total"].sum() > 0:
        st.bar_chart(seg_df.set_index("Fit Range")[["Total", "Applied", "Interviewed"]])
except Exception:
    pass

st.divider()

# ---------------------------------------------------------------------------
# Claude pattern analysis
# ---------------------------------------------------------------------------

st.subheader("Claude Pattern Analysis")
if pipeline["applied"] >= 3 or outreach["sent"] >= 3:
    if st.button("🤖 Analyze Patterns", type="primary"):
        with st.spinner("Analyzing with Claude..."):
            try:
                from tools.llm import ClaudeClient, load_prompt
                segments_text = "\n".join(
                    f"- {s['segment']}: {s['total']} jobs, {s['applied']} applied, {s['interviewed']} interviews"
                    for s in segments
                )
                prompt = load_prompt(
                    "analytics_summary",
                    pipeline_stats=str(pipeline),
                    outreach_stats=str(outreach),
                    outcome_stats=str(pipeline.get("outcome_stages", {})),
                    top_segments=segments_text,
                )
                result = ClaudeClient().chat_json(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=512,
                )
                patterns = result.get("patterns", [])
                recs = result.get("recommendations", [])
                if patterns:
                    st.subheader("Patterns")
                    for p in patterns:
                        st.info(f"• {p}")
                if recs:
                    st.subheader("Recommendations")
                    for r in recs:
                        st.success(f"→ {r}")
            except Exception as e:
                st.error(f"Analysis failed: {e}")
else:
    st.caption("Need 3+ applications or outreach sequences to unlock pattern analysis.")

st.divider()

# ---------------------------------------------------------------------------
# Log interview outcome
# ---------------------------------------------------------------------------

st.subheader("Log Interview Outcome")

@st.cache_data(ttl=30)
def load_applied_jobs():
    from db.session import get_session
    from db.models import Job
    with get_session() as db:
        jobs = db.query(Job).filter(Job.status == "applied").all()
    return [(j.id, j.title, j.company) for j in jobs]


applied_jobs = load_applied_jobs()
if not applied_jobs:
    st.caption("No applied jobs yet. Mark a job as applied first.")
else:
    outcome_labels = {f"{t} @ {c} (ID {i})": i for i, t, c in applied_jobs}
    sel = st.selectbox("Select job", list(outcome_labels.keys()))
    sel_job_id = outcome_labels[sel]

    STAGES = ["phone_screen", "technical", "onsite", "final", "offer"]
    stage = st.selectbox("Stage reached", STAGES, format_func=lambda s: s.replace("_", " ").title())
    rejection = st.text_input("Rejection reason (optional)")
    feedback = st.text_area("Feedback received (optional)", height=80)

    if st.button("Save Outcome"):
        from db.session import get_session
        from db.models import InterviewOutcome
        with get_session() as db:
            existing = db.query(InterviewOutcome).filter(InterviewOutcome.job_id == sel_job_id).first()
            if existing:
                existing.stage_reached = stage
                existing.rejection_reason = rejection
                existing.feedback = feedback
            else:
                db.add(InterviewOutcome(
                    job_id=sel_job_id,
                    stage_reached=stage,
                    rejection_reason=rejection,
                    feedback=feedback,
                ))
        st.success(f"Outcome saved: reached {stage.replace('_', ' ')}.")
        st.cache_data.clear()

        if feedback and rejection:
            with st.spinner("Analyzing feedback for study topics..."):
                try:
                    from tools.llm import ClaudeClient
                    result = ClaudeClient().chat_json(
                        messages=[{"role": "user", "content": (
                            f"Rejection reason: {rejection}\nFeedback: {feedback}\n\n"
                            "Give 1-3 specific technical topics to study based on this rejection. "
                            'Return JSON: {"study_topics": ["topic1"]}'
                        )}],
                        max_tokens=256,
                    )
                    topics = result.get("study_topics", [])
                    if topics:
                        st.subheader("Suggested Study Topics")
                        for t in topics:
                            st.markdown(f"• {t}")
                except Exception:
                    pass
