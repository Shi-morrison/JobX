"""Analytics & Feedback Loop (Phase 7.1 + 7.2).

7.1 — Response Rate Analyzer:
  Queries OutreachSequence and Application tables to compute response rates.
  Claude summarizes patterns and gives recommendations.

7.2 — Interview Outcome Tracker:
  `python main.py outcome --job-id <id>` logs interview result.
  Claude analyzes patterns across all outcomes.
"""

from datetime import datetime
from collections import defaultdict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from db.session import get_session
from db.models import Job, Application, OutreachSequence, Contact, InterviewOutcome
from tools.llm import ClaudeClient, load_prompt

console = Console()

STAGES = ["phone_screen", "technical", "onsite", "final", "offer"]


# ---------------------------------------------------------------------------
# 7.1 — Response Rate Analyzer
# ---------------------------------------------------------------------------

def compute_pipeline_stats() -> dict:
    """Compute application pipeline statistics from the DB."""
    with get_session() as db:
        jobs = db.query(Job).all()
        applications = db.query(Application).all()
        outcomes = db.query(InterviewOutcome).all()

    total_jobs = len(jobs)
    scored = sum(1 for j in jobs if j.fit_score)
    applied = sum(1 for j in jobs if j.status == "applied")
    avg_score = (
        sum(j.fit_score for j in jobs if j.fit_score) / scored
        if scored else 0
    )

    outcome_stages = defaultdict(int)
    for o in outcomes:
        outcome_stages[o.stage_reached or "unknown"] += 1

    return {
        "total_jobs_in_db": total_jobs,
        "scored": scored,
        "applied": applied,
        "avg_fit_score": round(avg_score, 1),
        "outcome_stages": dict(outcome_stages),
    }


def compute_outreach_stats() -> dict:
    """Compute outreach response rates."""
    with get_session() as db:
        seqs = db.query(OutreachSequence).all()

    total = len(seqs)
    sent = sum(1 for s in seqs if s.status in ("sent", "followed_up", "responded", "ghosted"))
    responded = sum(1 for s in seqs if s.response_received)
    ghosted = sum(1 for s in seqs if s.status == "ghosted")
    pending = sum(1 for s in seqs if s.status == "pending")

    response_rate = round(responded / sent * 100, 1) if sent else 0

    return {
        "total_sequences": total,
        "sent": sent,
        "pending": pending,
        "responded": responded,
        "ghosted": ghosted,
        "response_rate_pct": response_rate,
    }


def compute_top_segments() -> list[dict]:
    """Find company/score segments with best outcomes."""
    with get_session() as db:
        jobs = db.query(Job).filter(Job.fit_score.isnot(None)).all()
        outcomes = {o.job_id: o for o in db.query(InterviewOutcome).all()}

    # Bucket by score range
    buckets = {
        "9-10 (high fit)": [],
        "7-8 (good fit)": [],
        "5-6 (okay fit)": [],
        "1-4 (low fit)": [],
    }
    for j in jobs:
        s = j.fit_score or 0
        if s >= 9:
            buckets["9-10 (high fit)"].append(j)
        elif s >= 7:
            buckets["7-8 (good fit)"].append(j)
        elif s >= 5:
            buckets["5-6 (okay fit)"].append(j)
        else:
            buckets["1-4 (low fit)"].append(j)

    segments = []
    for label, bucket_jobs in buckets.items():
        applied = sum(1 for j in bucket_jobs if j.status == "applied")
        interviewed = sum(1 for j in bucket_jobs if j.id in outcomes)
        segments.append({
            "segment": label,
            "total": len(bucket_jobs),
            "applied": applied,
            "interviewed": interviewed,
        })
    return segments


def run_analytics() -> None:
    """CLI entry point: python main.py analytics"""
    console.print("\n[bold]Job Search Analytics[/bold]\n")

    pipeline = compute_pipeline_stats()
    outreach = compute_outreach_stats()
    segments = compute_top_segments()

    # Pipeline table
    p_table = Table(title="Application Pipeline", show_lines=False)
    p_table.add_column("Metric")
    p_table.add_column("Value", justify="right")
    p_table.add_row("Total jobs in DB", str(pipeline["total_jobs_in_db"]))
    p_table.add_row("Scored", str(pipeline["scored"]))
    p_table.add_row("Applied", str(pipeline["applied"]))
    p_table.add_row("Avg fit score", f"{pipeline['avg_fit_score']}/10")
    for stage, count in pipeline["outcome_stages"].items():
        p_table.add_row(f"  Reached: {stage}", str(count))
    console.print(p_table)
    console.print()

    # Outreach table
    o_table = Table(title="Outreach", show_lines=False)
    o_table.add_column("Metric")
    o_table.add_column("Value", justify="right")
    o_table.add_row("Sequences generated", str(outreach["total_sequences"]))
    o_table.add_row("Sent", str(outreach["sent"]))
    o_table.add_row("Pending (not sent)", str(outreach["pending"]))
    o_table.add_row("Responded", str(outreach["responded"]))
    o_table.add_row("Ghosted", str(outreach["ghosted"]))
    rate_color = "green" if outreach["response_rate_pct"] >= 20 else "yellow" if outreach["response_rate_pct"] >= 10 else "red"
    o_table.add_row("Response rate", f"[{rate_color}]{outreach['response_rate_pct']}%[/{rate_color}]")
    console.print(o_table)
    console.print()

    # Segments table
    s_table = Table(title="Outcomes by Fit Score", show_lines=False)
    s_table.add_column("Fit Score Range")
    s_table.add_column("Total", justify="right")
    s_table.add_column("Applied", justify="right")
    s_table.add_column("Interviewed", justify="right")
    for seg in segments:
        s_table.add_row(seg["segment"], str(seg["total"]), str(seg["applied"]), str(seg["interviewed"]))
    console.print(s_table)
    console.print()

    # Claude synthesis (only if there's enough data)
    if pipeline["applied"] >= 3 or outreach["sent"] >= 3:
        with console.status("Analyzing patterns with Claude..."):
            try:
                segments_text = "\n".join(
                    f"- {s['segment']}: {s['total']} jobs, {s['applied']} applied, {s['interviewed']} interviews"
                    for s in segments
                )
                prompt = load_prompt(
                    "analytics_summary",
                    pipeline_stats=str(pipeline),
                    outreach_stats=str(outreach),
                    outcome_stats=str(pipeline["outcome_stages"]),
                    top_segments=segments_text,
                )
                client = ClaudeClient()
                result = client.chat_json(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=512,
                )
                patterns = result.get("patterns", [])
                recs = result.get("recommendations", [])

                lines = []
                if patterns:
                    lines.append("[bold]Patterns:[/bold]")
                    for p in patterns:
                        lines.append(f"  • {p}")
                if recs:
                    lines.append("\n[bold]Recommendations:[/bold]")
                    for r in recs:
                        lines.append(f"  → {r}")

                if lines:
                    console.print(Panel("\n".join(lines), title="Claude Analysis", border_style="blue"))
            except Exception as e:
                console.print(f"[dim]Claude analysis skipped: {e}[/dim]")
    else:
        console.print("[dim]Apply to more jobs to unlock Claude pattern analysis (needs 3+ applications).[/dim]")


# ---------------------------------------------------------------------------
# 7.2 — Interview Outcome Tracker
# ---------------------------------------------------------------------------

def run_outcome(job_id: int) -> None:
    """CLI entry point: python main.py outcome --job-id <id>

    Interactive prompt to log an interview outcome.
    """
    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        console.print(f"[red]No job found with ID {job_id}.[/red]")
        return

    console.print(f"\n[bold]Log Outcome:[/bold] {job.title} @ {job.company}\n")

    # Stage reached
    console.print("Stage reached:")
    for i, stage in enumerate(STAGES, 1):
        console.print(f"  {i}. {stage.replace('_', ' ').title()}")
    stage_input = typer.prompt("Enter number", default="1")
    try:
        stage = STAGES[int(stage_input) - 1]
    except (ValueError, IndexError):
        stage = "phone_screen"

    rejection_reason = ""
    feedback = ""
    if stage != "offer":
        rejection_reason = typer.prompt(
            "Rejection reason (or press Enter to skip)", default=""
        )
        feedback = typer.prompt(
            "Any feedback received (or press Enter to skip)", default=""
        )
    else:
        console.print("[green]Congratulations on the offer![/green]")

    # Save to DB
    with get_session() as db:
        existing = db.query(InterviewOutcome).filter(
            InterviewOutcome.job_id == job_id
        ).first()
        if existing:
            existing.stage_reached = stage
            existing.rejection_reason = rejection_reason
            existing.feedback = feedback
        else:
            outcome = InterviewOutcome(
                job_id=job_id,
                stage_reached=stage,
                rejection_reason=rejection_reason,
                feedback=feedback,
            )
            db.add(outcome)

    console.print(f"\n[green]✓[/green] Outcome logged: reached [bold]{stage}[/bold] at {job.company}")

    # Update study plan if feedback mentions specific gaps
    if feedback and rejection_reason:
        console.print("\n[dim]Analyzing feedback for study plan updates...[/dim]")
        try:
            client = ClaudeClient()
            analysis = client.chat_json(
                messages=[{"role": "user", "content": (
                    f"A software engineer was rejected at the {stage} stage for a "
                    f"{job.title} role at {job.company}.\n\n"
                    f"Rejection reason: {rejection_reason}\n"
                    f"Feedback: {feedback}\n\n"
                    "Identify 1-3 specific technical or behavioral topics to study "
                    "based on this rejection. Be concrete (e.g. 'system design: consistent hashing', "
                    "not 'study algorithms').\n\n"
                    'Return JSON: {"study_topics": ["topic1", "topic2"]}'
                )}],
                max_tokens=256,
            )
            topics = analysis.get("study_topics", [])
            if topics:
                console.print("[bold]Suggested study topics based on this rejection:[/bold]")
                for t in topics:
                    console.print(f"  • {t}")
                console.print(
                    "[dim]Re-run prep to get updated questions: "
                    f"python main.py prep run --job-id {job_id} --force[/dim]"
                )
        except Exception:
            pass
