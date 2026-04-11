"""Hiring Signal Detector (Phase 4.3).

Identifies companies that are actively ramping up engineering hiring.

Two signal sources:
  1. Job posting velocity  — 3+ eng roles posted within the last N days in our DB
  2. SerpAPI "we're hiring" — LinkedIn/web posts where employees announce open roles
     (optional — only runs if SERPAPI_KEY is configured)

Signals are computed on-the-fly from the jobs table; no separate DB table required.
They are used to surface high-priority companies in the `jobs` and `signals` commands.
"""

from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from db.session import get_session
from db.models import Job

console = Console()


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------

def get_surge_companies(
    days: int = 7,
    min_jobs: int = 3,
) -> list[dict]:
    """Return companies with posting velocity >= min_jobs in the last `days` days.

    Returns:
        List of dicts sorted by job_count descending:
        [{"company": str, "job_count": int, "titles": [str], "latest_posted": datetime|None}]
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_session() as db:
        jobs = db.query(Job).filter(
            Job.created_at >= cutoff,
        ).all()

    # Group by company
    company_map: dict[str, dict] = {}
    for job in jobs:
        co = job.company
        if co not in company_map:
            company_map[co] = {"company": co, "job_count": 0, "titles": [], "latest_posted": None}
        company_map[co]["job_count"] += 1
        company_map[co]["titles"].append(job.title)
        if job.posted_date:
            prev = company_map[co]["latest_posted"]
            if prev is None or job.posted_date > prev:
                company_map[co]["latest_posted"] = job.posted_date

    surges = [v for v in company_map.values() if v["job_count"] >= min_jobs]
    return sorted(surges, key=lambda x: x["job_count"], reverse=True)


def is_surge(company_name: str, days: int = 7, min_jobs: int = 3) -> bool:
    """Return True if the company has a hiring surge signal."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_session() as db:
        count = db.query(Job).filter(
            Job.company == company_name,
            Job.created_at >= cutoff,
        ).count()
    return count >= min_jobs


def get_surge_companies_set(days: int = 7, min_jobs: int = 3) -> set[str]:
    """Return the set of company names currently showing a hiring surge.

    Efficient: O(1) lookup for the `jobs` display command.
    """
    return {s["company"] for s in get_surge_companies(days=days, min_jobs=min_jobs)}


# ---------------------------------------------------------------------------
# Optional: SerpAPI "we're hiring" signals
# ---------------------------------------------------------------------------

def check_hiring_posts(company_name: str) -> list[dict]:
    """Search for public "we're hiring" signals using SerpAPI.

    Returns [] if SERPAPI_KEY is not configured.
    """
    try:
        from tools.search import search_web
        results = search_web(
            f'site:linkedin.com "{company_name}" "we\'re hiring" OR "we are hiring" OR "join our team" software engineer',
            num_results=3,
        )
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# CLI display
# ---------------------------------------------------------------------------

def run_signals(days: int = 7, min_jobs: int = 3, serpapi: bool = False) -> None:
    """CLI entry point: python main.py signals"""
    console.print(f"\n[bold]Hiring Signal Detector[/bold] — last {days} days\n")

    surges = get_surge_companies(days=days, min_jobs=min_jobs)

    if not surges:
        console.print(
            f"[dim]No companies with {min_jobs}+ postings in the last {days} days.[/dim]"
        )
        console.print(
            "[dim]Run [bold]python main.py search[/bold] to scrape more jobs, "
            "then re-run signals.[/dim]"
        )
        return

    table = Table(title=f"[green]{len(surges)} Companies with Hiring Surge[/green]", show_lines=True)
    table.add_column("Company", style="bold")
    table.add_column("Jobs (last {days}d)".format(days=days), justify="center", width=16)
    table.add_column("Sample Roles")
    table.add_column("Latest Posted")

    for s in surges:
        sample = ", ".join(s["titles"][:3])
        if len(s["titles"]) > 3:
            sample += f" +{len(s['titles']) - 3} more"
        latest = s["latest_posted"].strftime("%Y-%m-%d") if s["latest_posted"] else "—"
        table.add_row(
            s["company"],
            f"[green]{s['job_count']}[/green]",
            sample,
            latest,
        )

    console.print(table)

    # Optional SerpAPI enrichment
    if serpapi:
        console.print("\n[dim]Checking SerpAPI for 'we're hiring' posts...[/dim]")
        for s in surges[:5]:
            posts = check_hiring_posts(s["company"])
            if posts:
                console.print(f"  [bold]{s['company']}[/bold]: {posts[0]['title']}")

    console.print()
    console.print(
        "[dim]Tip: Research high-signal companies with "
        "[bold]python main.py research --company \"<name>\"[/bold][/dim]"
    )
    console.print(
        "[dim]View their jobs with: [bold]python main.py jobs --search \"<name>\"[/bold][/dim]"
    )
