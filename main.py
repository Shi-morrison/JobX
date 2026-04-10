import typer
from rich.console import Console

app = typer.Typer(help="JobX — AI-powered job application agent suite")
db_app = typer.Typer(help="Database management commands")
prep_app = typer.Typer(help="Interview prep commands")
app.add_typer(db_app, name="db")
app.add_typer(prep_app, name="prep")

console = Console()


# ---------------------------------------------------------------------------
# db commands
# ---------------------------------------------------------------------------

@db_app.command("init")
def db_init():
    """Initialize the database and run migrations."""
    from db.session import init_db
    init_db()
    console.print("[green]Database initialized.[/green]")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

@app.command()
def search(
    hours_back: int = typer.Option(
        None,
        "--hours-back",
        help="Hours back to search. Auto-calculates from last run if omitted (default 24h on first run).",
    ),
    location: str = typer.Option(
        None,
        "--location",
        help="Location to search. Use 'Remote' for remote jobs, or a city like 'New York'. Case-insensitive. Overrides TARGET_LOCATIONS in .env for this run.",
    ),
    level: str = typer.Option(
        None,
        "--level",
        help="Seniority level: intern, junior, mid, senior, staff. Prepended to each search term.",
    ),
    results: int = typer.Option(
        15,
        "--results",
        help="Max listings to fetch per role/location combination. Lower = faster. Default: 15.",
    ),
):
    """Scrape new job listings and store them in the database.

    Examples:

      python main.py search

      python main.py search --location remote --level senior

      python main.py search --location "New York" --hours-back 48 --results 20
    """
    from tools.scraper import run_scraper
    run_scraper(
        hours_back=hours_back,
        location_override=location,
        level=level,
        results_per_query=results,
    )


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------

@app.command()
def score(
    job_id: int = typer.Option(
        None,
        "--job-id",
        help="Score a single specific job by ID. Find IDs with: python main.py jobs",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        help="Max number of jobs to score in this run. Useful for testing before committing to a full batch.",
    ),
    min_score: int = typer.Option(
        None,
        "--min-score",
        help="Only display jobs at or above this fit score (1-10). All jobs are still scored and saved.",
    ),
    show_reasoning: bool = typer.Option(
        False,
        "--show-reasoning",
        help="Print Claude's reasoning for each scored job.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-score jobs that have already been scored. Without this flag, only unscored jobs are processed.",
    ),
    recent: bool = typer.Option(
        False,
        "--recent",
        help="Score most recently posted jobs first. Use with --limit to target freshest listings (fewest applicants).",
    ),
):
    """Score jobs using Claude: fit score, ATS keyword check, and gap analysis.

    By default scores all unscored jobs. Use flags to narrow the scope.

    Examples:

      python main.py score                              # score all unscored jobs

      python main.py score --limit 5                   # score next 5 unscored jobs

      python main.py score --recent --limit 10         # score 10 most recently posted unscored jobs

      python main.py score --recent --force --limit 10 # re-score 10 most recent jobs

      python main.py score --job-id 12                 # score one specific job

      python main.py score --force --job-id 12         # re-score an already-scored job

      python main.py score --min-score 7 --show-reasoning
    """
    from agents.scorer import run_scorer
    run_scorer(
        job_id=job_id,
        limit=limit,
        min_score=min_score,
        show_reasoning=show_reasoning,
        force=force,
        recent=recent,
    )


# ---------------------------------------------------------------------------
# jobs
# ---------------------------------------------------------------------------

@app.command()
def jobs(
    min_score: int = typer.Option(None, "--min-score", help="Only show jobs at or above this fit score."),
    limit: int = typer.Option(25, "--limit", help="Max number of jobs to show. Default: 25."),
    unscored: bool = typer.Option(False, "--unscored", help="Show only jobs that have not been scored yet (use to find IDs for --job-id)."),
    all_jobs_flag: bool = typer.Option(False, "--all", help="Show all jobs — scored, unscored, and applied."),
    applied: bool = typer.Option(False, "--applied", help="Show only jobs you have marked as applied."),
    search: str = typer.Option(None, "--search", help="Filter by keyword in job title or company name. Case-insensitive."),
):
    """List jobs ranked by fit score. Applied jobs are hidden by default.

    Use --unscored to find IDs of jobs not yet scored.
    Use --search to find a specific job by title or company.
    Use --applied to review your application pipeline.

    Examples:

      python main.py jobs                        # scored jobs ranked by fit score

      python main.py jobs --search "stripe"      # find jobs at Stripe

      python main.py jobs --search "ML"          # find ML-related jobs

      python main.py jobs --unscored             # unscored jobs (find IDs to score)

      python main.py jobs --applied              # jobs you have marked as applied

      python main.py jobs --all                  # every job in the database

      python main.py jobs --min-score 7          # only high-fit scored jobs
    """
    from db.session import get_session
    from db.models import Job
    from rich.table import Table

    with get_session() as db:
        if applied:
            query = db.query(Job).filter(Job.status == "applied")
            query = query.order_by(Job.fit_score.desc().nulls_last())
        elif unscored:
            query = db.query(Job).filter(
                Job.fit_score.is_(None),
                Job.status != "applied",
            )
            query = query.order_by(Job.posted_date.desc().nulls_last())
        elif all_jobs_flag:
            query = db.query(Job)
            query = query.order_by(Job.fit_score.desc().nulls_last())
        else:
            # Default: scored jobs that are not applied
            query = db.query(Job).filter(
                Job.fit_score.isnot(None),
                Job.status != "applied",
            )
            if min_score:
                query = query.filter(Job.fit_score >= min_score)
            query = query.order_by(Job.fit_score.desc())

        if search:
            keyword = f"%{search}%"
            query = query.filter(
                Job.title.ilike(keyword) | Job.company.ilike(keyword)
            )

        result = query.limit(limit).all()

    if not result:
        if applied:
            console.print("[yellow]No applied jobs found. Mark one with: [bold]python main.py mark-applied --job-id <id>[/bold][/yellow]")
        elif unscored:
            console.print("[yellow]No unscored jobs found. Run [bold]python main.py search[/bold] to scrape listings.[/yellow]")
        elif all_jobs_flag:
            console.print("[yellow]No jobs in database. Run [bold]python main.py search[/bold] first.[/yellow]")
        elif search:
            console.print(f"[yellow]No jobs found matching '{search}'.[/yellow]")
        else:
            console.print("[yellow]No scored jobs found. Run [bold]python main.py score[/bold] first.[/yellow]")
        return

    if applied:
        title = f"[blue]{len(result)} Applied Jobs[/blue]"
    elif unscored:
        title = f"[yellow]{len(result)} Unscored Jobs[/yellow]"
    elif all_jobs_flag:
        title = f"[green]{len(result)} All Jobs[/green]"
    else:
        label = f" matching '{search}'" if search else ""
        title = f"[green]{len(result)} Scored Jobs{label}[/green]"

    table = Table(title=title, show_lines=True)
    table.add_column("ID", style="dim", width=5)
    table.add_column("Fit", width=6, justify="center")
    table.add_column("ATS%", width=6, justify="center")
    table.add_column("Title", style="bold")
    table.add_column("Company")
    table.add_column("Status", width=10)
    table.add_column("Posted")

    for job in result:
        if job.fit_score is not None:
            score_color = "green" if job.fit_score >= 7 else "yellow" if job.fit_score >= 5 else "red"
            fit_str = f"[{score_color}]{job.fit_score}/10[/{score_color}]"
        else:
            fit_str = "[dim]—[/dim]"
        ats = f"{job.ats_score:.0f}%" if job.ats_score is not None else "—"
        posted = job.posted_date.strftime("%Y-%m-%d") if job.posted_date else "—"
        status_color = "blue" if job.status == "applied" else "dim"
        table.add_row(
            str(job.id),
            fit_str,
            ats,
            job.title,
            job.company,
            f"[{status_color}]{job.status or '—'}[/{status_color}]",
            posted,
        )

    console.print(table)
    if applied:
        console.print("[dim]Run [bold]python main.py show --job-id <id>[/bold] for full details on any job.[/dim]")
    elif unscored:
        console.print("[dim]Score a specific job with: [bold]python main.py score --job-id <id>[/bold][/dim]")
    else:
        console.print("[dim]Run [bold]python main.py show --job-id <id>[/bold] for full details. Mark applied: [bold]python main.py mark-applied --job-id <id>[/bold][/dim]")


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

@app.command()
def show(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to show full details for."),
):
    """Show full details for a scored job: fit score, ATS%, fit reasoning, gap analysis, reframe suggestions.

    Find job IDs by running: python main.py jobs
    Find unscored job IDs with: python main.py jobs --unscored
    """
    from db.session import get_session
    from db.models import Job
    from rich.panel import Panel
    from rich.text import Text

    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        console.print(f"[red]No job found with ID {job_id}.[/red]")
        raise typer.Exit(1)

    # Header
    score_color = "green" if (job.fit_score or 0) >= 7 else "yellow" if (job.fit_score or 0) >= 5 else "red"
    fit = f"[{score_color}]{job.fit_score}/10[/{score_color}]" if job.fit_score else "[dim]unscored[/dim]"
    ats = f"{job.ats_score:.0f}%" if job.ats_score is not None else "[dim]—[/dim]"

    console.print(Panel(
        f"[bold]{job.title}[/bold] @ {job.company}\n"
        f"Source: {job.source or '—'}   Status: {job.status}   Job ID: {job.id}\n"
        f"URL: [link={job.url}]{job.url}[/link]",
        title="Job Details",
        expand=False,
    ))

    console.print(f"\n[bold]Fit Score:[/bold]  {fit}    [bold]ATS Coverage:[/bold]  {ats}\n")

    gaps = job.gap_analysis or {}

    if gaps.get("fit_reasoning"):
        console.print("[bold]Fit Reasoning:[/bold]")
        console.print(f"  [dim]{gaps['fit_reasoning']}[/dim]")
        console.print()

    if gaps.get("hard_gaps"):
        console.print("[bold red]Hard Gaps[/bold red] (genuinely missing — hard to reframe):")
        for g in gaps["hard_gaps"]:
            console.print(f"  • {g}")
        console.print()

    if gaps.get("soft_gaps"):
        console.print("[bold yellow]Soft Gaps[/bold yellow] (can reframe using your experience):")
        for g in gaps["soft_gaps"]:
            console.print(f"  • {g}")
        console.print()

    if gaps.get("reframe_suggestions"):
        console.print("[bold green]Reframe Suggestions[/bold green]:")
        for s in gaps["reframe_suggestions"]:
            console.print(f"  [bold]{s['gap']}[/bold]")
            console.print(f"    → {s['suggestion']}")
        console.print()

    if job.description:
        console.print(f"[bold]Job Description Preview:[/bold]")
        console.print(f"[dim]{job.description[:600]}...[/dim]")


# ---------------------------------------------------------------------------
# mark-applied
# ---------------------------------------------------------------------------

@app.command(name="mark-applied")
def mark_applied(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to mark as applied."),
):
    """Mark a job as applied. Applied jobs are hidden from the default jobs list.

    Find the job ID with: python main.py jobs --search "company name"
    View applied jobs with: python main.py jobs --applied

    Example:

      python main.py mark-applied --job-id 12
    """
    from db.session import get_session
    from db.models import Job

    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            console.print(f"[red]No job found with ID {job_id}. Find IDs with: python main.py jobs[/red]")
            raise typer.Exit(1)
        if job.status == "applied":
            console.print(f"[yellow]Job {job_id} ({job.title} @ {job.company}) is already marked as applied.[/yellow]")
            return
        prev_status = job.status
        job.status = "applied"

    console.print(f"[green]Marked as applied:[/green] {job.title} @ {job.company} (ID {job_id})")
    console.print(f"[dim]Status changed: {prev_status} → applied[/dim]")
    console.print(f"[dim]View all applied jobs: python main.py jobs --applied[/dim]")


# ---------------------------------------------------------------------------
# research
# ---------------------------------------------------------------------------

@app.command()
def research(company: str = typer.Option(..., help="Company name to research")):
    """Run company research agent."""
    console.print(f"[yellow]Research command for '{company}' — coming in Phase 4.[/yellow]")


# ---------------------------------------------------------------------------
# salary
# ---------------------------------------------------------------------------

@app.command()
def salary(
    company: str = typer.Option(..., help="Company name"),
    level: str = typer.Option(..., help="Role level: junior/mid/senior"),
):
    """Get salary intelligence for a company and level."""
    console.print(f"[yellow]Salary command — coming in Phase 4.[/yellow]")


# ---------------------------------------------------------------------------
# prep
# ---------------------------------------------------------------------------

@prep_app.command("run")
def prep_run(job_id: int = typer.Option(..., help="Job ID to prepare for")):
    """Generate interview prep for a job."""
    console.print(f"[yellow]Prep command for job {job_id} — coming in Phase 3.5.[/yellow]")


@prep_app.command("mock")
def prep_mock(job_id: int = typer.Option(..., help="Job ID for mock interview")):
    """Start an interactive mock interview session."""
    console.print(f"[yellow]Mock interview for job {job_id} — coming in Phase 3.5.[/yellow]")


# ---------------------------------------------------------------------------
# referrals
# ---------------------------------------------------------------------------

@app.command()
def referrals(job_id: int = typer.Option(..., help="Job ID to check connections for")):
    """Cross-reference LinkedIn connections against a job's company."""
    console.print(f"[yellow]Referrals command — coming in Phase 5.[/yellow]")


# ---------------------------------------------------------------------------
# outreach
# ---------------------------------------------------------------------------

@app.command()
def outreach(
    job_id: int = typer.Option(None, help="Job ID to find contacts for"),
    due: bool = typer.Option(False, "--due", help="Show follow-ups due today"),
):
    """Find contacts and generate outreach messages, or show follow-ups due today."""
    console.print("[yellow]Outreach command — coming in Phase 5.[/yellow]")


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

@app.command()
def apply(job_id: int = typer.Option(..., help="Job ID to apply for")):
    """Auto-fill and submit an application via Playwright."""
    console.print(f"[yellow]Apply command for job {job_id} — coming in Phase 6.[/yellow]")


# ---------------------------------------------------------------------------
# outcome
# ---------------------------------------------------------------------------

@app.command()
def outcome(job_id: int = typer.Option(..., help="Job ID to log outcome for")):
    """Log an interview outcome for a job."""
    console.print(f"[yellow]Outcome command for job {job_id} — coming in Phase 7.[/yellow]")


# ---------------------------------------------------------------------------
# digest
# ---------------------------------------------------------------------------

@app.command()
def digest():
    """Show the daily summary dashboard."""
    console.print("[yellow]Digest command — coming in Phase 7.[/yellow]")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
