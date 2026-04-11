"""Daily Digest (Phase 7.3).

`python main.py digest` — the daily driver command.

Sections:
  1. New jobs ranked by fit score (scored since yesterday)
  2. Follow-ups due today
  3. Hiring surge signals
  4. Pipeline summary (applied / interviewing / offers)
  5. Study plan items (from most recent prep session)
"""

from datetime import datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

from db.session import get_session
from db.models import Job, Application, InterviewPrep, OutreachSequence

console = Console()


def _pipeline_summary() -> dict:
    """Quick counts by job status."""
    with get_session() as db:
        jobs = db.query(Job).all()

    counts = {"new": 0, "scored": 0, "applied": 0, "interviewing": 0, "offer": 0, "rejected": 0}
    for j in jobs:
        status = j.status or "new"
        if status in counts:
            counts[status] += 1
        elif j.fit_score and status == "new":
            counts["scored"] += 1
    return counts


def _new_scored_jobs(since_hours: int = 24) -> list:
    """Jobs scored in the last `since_hours` hours, sorted by fit score."""
    cutoff = datetime.utcnow() - timedelta(hours=since_hours)
    with get_session() as db:
        jobs = db.query(Job).filter(
            Job.fit_score.isnot(None),
            Job.created_at >= cutoff,
        ).order_by(Job.fit_score.desc()).limit(10).all()
    return jobs


def _due_followups_count() -> int:
    """Count outreach sequences with follow_up_due <= now."""
    now = datetime.utcnow()
    with get_session() as db:
        return db.query(OutreachSequence).filter(
            OutreachSequence.follow_up_due <= now,
            OutreachSequence.response_received == False,  # noqa: E712
            OutreachSequence.status.in_(["sent", "followed_up"]),
        ).count()


def _study_items() -> list[str]:
    """Get the most recent study plan topics across all prep sessions."""
    with get_session() as db:
        prep = db.query(InterviewPrep).order_by(
            InterviewPrep.created_at.desc()
        ).first()

    if not prep or not prep.study_plan:
        return []

    items = []
    plan = prep.study_plan
    if isinstance(plan, list):
        for item in plan[:5]:
            if isinstance(item, dict):
                topic = item.get("topic", "")
                hours = item.get("hours", "")
                if topic:
                    items.append(f"{topic}" + (f" ({hours}h)" if hours else ""))
            elif isinstance(item, str):
                items.append(item)
    return items


def run_digest() -> None:
    """CLI entry point: python main.py digest"""
    now = datetime.now()
    console.print()
    console.print(Panel(
        f"[bold]JobX Daily Digest[/bold]   {now.strftime('%A, %B %d %Y')}",
        border_style="blue",
    ))
    console.print()

    # 1. Pipeline summary
    counts = _pipeline_summary()
    console.print(Rule("[bold]Pipeline[/bold]"))
    pipeline_parts = []
    if counts["scored"]:
        pipeline_parts.append(f"[green]{counts['scored']} scored[/green]")
    if counts["applied"]:
        pipeline_parts.append(f"[blue]{counts['applied']} applied[/blue]")
    if counts["interviewing"]:
        pipeline_parts.append(f"[yellow]{counts['interviewing']} interviewing[/yellow]")
    if counts["offer"]:
        pipeline_parts.append(f"[bold green]{counts['offer']} offer(s)![/bold green]")
    if counts["rejected"]:
        pipeline_parts.append(f"[dim]{counts['rejected']} rejected[/dim]")
    if pipeline_parts:
        console.print("  " + "   ·   ".join(pipeline_parts))
    else:
        console.print("  [dim]No jobs in pipeline yet. Run: python main.py search[/dim]")
    console.print()

    # 2. New scored jobs (last 24h)
    new_jobs = _new_scored_jobs(since_hours=24)
    console.print(Rule("[bold]New Jobs (last 24h)[/bold]"))
    if new_jobs:
        table = Table(show_header=True, show_lines=False, box=None, pad_edge=False)
        table.add_column("Fit", width=6, justify="center")
        table.add_column("Title", style="bold")
        table.add_column("Company")
        table.add_column("ID", style="dim", width=6)
        for j in new_jobs:
            score_color = "green" if j.fit_score >= 7 else "yellow" if j.fit_score >= 5 else "red"
            table.add_row(
                f"[{score_color}]{j.fit_score}/10[/{score_color}]",
                j.title,
                j.company,
                str(j.id),
            )
        console.print(table)
        console.print(
            f"  [dim]Show all: python main.py jobs   |   Details: python main.py show --job-id <id>[/dim]"
        )
    else:
        console.print("  [dim]No new scored jobs in the last 24h. Run: python main.py search && python main.py score[/dim]")
    console.print()

    # 3. Follow-ups due
    due_count = _due_followups_count()
    console.print(Rule("[bold]Follow-Ups[/bold]"))
    if due_count > 0:
        console.print(
            f"  [yellow]{due_count} follow-up(s) due today[/yellow]   "
            f"[dim]→ python main.py outreach --due[/dim]"
        )
    else:
        console.print("  [dim]No follow-ups due.[/dim]")
    console.print()

    # 4. Hiring surges
    console.print(Rule("[bold]Hiring Signals[/bold]"))
    try:
        from agents.hiring_signals import get_surge_companies
        surges = get_surge_companies(days=7, min_jobs=3)
        if surges:
            top = surges[:3]
            for s in top:
                console.print(
                    f"  [yellow]⚡[/yellow] [bold]{s['company']}[/bold] — "
                    f"{s['job_count']} postings in last 7 days"
                )
            if len(surges) > 3:
                console.print(f"  [dim]+{len(surges) - 3} more → python main.py signals[/dim]")
        else:
            console.print("  [dim]No hiring surges detected. Run: python main.py signals[/dim]")
    except Exception:
        console.print("  [dim]Hiring signals unavailable.[/dim]")
    console.print()

    # 5. Study plan
    study_items = _study_items()
    console.print(Rule("[bold]Study Plan[/bold]"))
    if study_items:
        for item in study_items:
            console.print(f"  • {item}")
        console.print(
            "  [dim]Full prep: python main.py prep run --job-id <id>[/dim]"
        )
    else:
        console.print(
            "  [dim]No study plan yet. Generate one: python main.py prep run --job-id <id>[/dim]"
        )
    console.print()

    # Footer
    console.print(Rule())
    console.print(
        "[dim]Analytics: python main.py analytics   |   "
        "All commands: python main.py --help[/dim]"
    )
    console.print()
