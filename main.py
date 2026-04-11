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
# parse-resume
# ---------------------------------------------------------------------------

@app.command(name="parse-resume")
def parse_resume_cmd(
    force: bool = typer.Option(False, "--force", help="Re-parse even if cache exists. Run this after updating data/base_resume.docx."),
):
    """Parse your base resume and cache the result.

    All agents (scorer, tailor, cover letter, prep) read from this cache.
    Replace data/base_resume.docx, then run this with --force before re-scoring.

    Examples:

      python main.py parse-resume           # parse if no cache exists

      python main.py parse-resume --force   # force re-parse after updating resume
    """
    from tools.llm import parse_resume
    from rich.console import Console
    _console = Console()

    if not force:
        from pathlib import Path
        if Path("data/resume_parsed.json").exists():
            _console.print("[yellow]Cache already exists. Use [bold]--force[/bold] to re-parse after updating your resume.[/yellow]")
            return

    with _console.status("Parsing resume..."):
        result = parse_resume(force=True)

    _console.print(f"[green]✓[/green] Resume parsed: [bold]{result.get('name', 'Unknown')}[/bold]")
    _console.print(f"  Skills found: {len(result.get('skills', []))}")
    _console.print(f"  Experience entries: {len(result.get('experience', []))}")
    _console.print("[dim]Cached to data/resume_parsed.json. Re-score jobs with: python main.py score --force[/dim]")


# ---------------------------------------------------------------------------
# fetch-descriptions
# ---------------------------------------------------------------------------

@app.command(name="fetch-descriptions")
def fetch_descriptions(
    limit: int = typer.Option(None, "--limit", help="Max number of jobs to backfill. Defaults to all."),
):
    """Fetch missing descriptions for LinkedIn jobs scraped without one.

    Hits LinkedIn's public job API for each job and stores the result.
    Adds a 1-3s delay between requests to avoid rate limiting.

    Examples:

      python main.py fetch-descriptions            # backfill all missing

      python main.py fetch-descriptions --limit 10 # backfill next 10
    """
    from tools.scraper import run_fetch_descriptions
    run_fetch_descriptions(limit=limit)


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
    limit: int = typer.Option(25, "--limit", help="Max number of jobs to show (default 25). Works with all flags — e.g. --recent --limit 50. Ignored when --all is used."),
    unscored: bool = typer.Option(False, "--unscored", help="Show only jobs that have not been scored yet (use to find IDs for --job-id)."),
    all_jobs_flag: bool = typer.Option(False, "--all", help="Show all jobs — scored, unscored, and applied."),
    applied: bool = typer.Option(False, "--applied", help="Show only jobs you have marked as applied."),
    search: str = typer.Option(None, "--search", help="Filter by keyword in job title or company name. Case-insensitive."),
    recent: bool = typer.Option(False, "--recent", help="Sort by most recently posted first instead of fit score."),
):
    """List jobs ranked by fit score. Applied jobs are hidden by default.

    Use --unscored to find IDs of jobs not yet scored.
    Use --search to find a specific job by title or company.
    Use --applied to review your application pipeline.
    Use --recent to sort by newest posted instead of fit score.

    Examples:

      python main.py jobs                        # scored jobs ranked by fit score

      python main.py jobs --recent               # scored jobs sorted by newest posted

      python main.py jobs --recent --limit 50    # 50 most recently posted scored jobs

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
    from agents.hiring_signals import get_surge_companies_set

    surge_companies = get_surge_companies_set()

    with get_session() as db:
        if applied:
            query = db.query(Job).filter(Job.status == "applied")
            order = Job.posted_date.desc().nulls_last() if recent else Job.fit_score.desc().nulls_last()
            query = query.order_by(order)
        elif unscored:
            query = db.query(Job).filter(
                Job.fit_score.is_(None),
                Job.status != "applied",
            )
            query = query.order_by(Job.posted_date.desc().nulls_last())
        elif all_jobs_flag:
            query = db.query(Job)
            order = Job.posted_date.desc().nulls_last() if recent else Job.fit_score.desc().nulls_last()
            query = query.order_by(order)
        else:
            # Default: scored jobs that are not applied
            query = db.query(Job).filter(
                Job.fit_score.isnot(None),
                Job.status != "applied",
            )
            if min_score:
                query = query.filter(Job.fit_score >= min_score)
            order = Job.posted_date.desc().nulls_last() if recent else Job.fit_score.desc()
            query = query.order_by(order)

        if search:
            keyword = f"%{search}%"
            query = query.filter(
                Job.title.ilike(keyword) | Job.company.ilike(keyword)
            )

        result = (query.all() if all_jobs_flag else query.limit(limit).all())

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
    table.add_column("JD", width=4, justify="center")
    table.add_column("⚡", width=3, justify="center")
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
        has_desc = bool(job.description and job.description.strip() not in ("", "nan"))
        jd_str = "[green]✓[/green]" if has_desc else "[red]✗[/red]"
        surge_str = "[yellow]⚡[/yellow]" if job.company in surge_companies else ""
        table.add_row(
            str(job.id),
            fit_str,
            ats,
            jd_str,
            surge_str,
            job.title,
            job.company,
            f"[{status_color}]{job.status or '—'}[/{status_color}]",
            posted,
        )

    console.print(table)
    if surge_companies:
        console.print(f"[dim]⚡ = hiring surge (3+ roles posted in last 7 days). See: [bold]python main.py signals[/bold][/dim]")
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
    has_description = job.description and job.description.strip() not in ("", "nan")

    # Hint when scoring data is missing (scored before ATS/reasoning were added, or no description)
    missing_ats = job.fit_score and job.ats_score is None
    missing_reasoning = job.fit_score and not gaps.get("fit_reasoning")
    if missing_ats or missing_reasoning:
        if has_description:
            console.print(f"[dim]Some scoring data is missing. Re-score to get full details: python main.py score --job-id {job_id} --force[/dim]")
        else:
            console.print(f"[dim]Some scoring data is missing. This job has no description — it cannot be re-scored.[/dim]")
        console.print()

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

    if has_description:
        console.print("[bold]Job Description Preview:[/bold]")
        console.print(f"[dim]{job.description[:600]}{'...' if len(job.description) > 600 else ''}[/dim]")
    else:
        console.print("[dim]No job description available for this listing.[/dim]")


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
# tailor
# ---------------------------------------------------------------------------

@app.command()
def tailor(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to tailor the resume for. Must be scored first."),
):
    """Tailor your resume for a specific job using gap analysis reframe suggestions.

    Reads data/base_resume.docx, rewrites relevant bullets to match the JD,
    and saves the result to data/resume_versions/resume_<id>.docx.
    Your base resume is never modified.

    Requires the job to be scored first: python main.py score --job-id <id>
    Find job IDs with: python main.py jobs

    Example:

      python main.py tailor --job-id 12
    """
    from agents.resume_tailor import run_tailor
    run_tailor(job_id=job_id)


# ---------------------------------------------------------------------------
# cover-letter
# ---------------------------------------------------------------------------

@app.command(name="cover-letter")
def cover_letter(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to generate a cover letter for. Must be scored first."),
):
    """Generate a tailored cover letter for a specific job.

    Saves the cover letter to data/cover_letters/cover_letter_<id>.docx.
    Uses gap analysis to address soft gaps and reframe your experience.

    Requires the job to be scored first: python main.py score --job-id <id>
    Find job IDs with: python main.py jobs

    Example:

      python main.py cover-letter --job-id 12
    """
    from agents.cover_letter import run_cover_letter
    run_cover_letter(job_id=job_id)


# ---------------------------------------------------------------------------
# research
# ---------------------------------------------------------------------------

@app.command()
def research(
    company: str = typer.Option(..., "--company", help="Company name to research."),
    force: bool = typer.Option(False, "--force", help="Re-research even if cached data exists."),
):
    """Research a company: funding stage, Glassdoor rating, tech stack, news, and layoff history.

    Results are cached in the database and automatically used to enrich cover letters
    and interview prep for any job at that company.

    Run this before generating a cover letter or interview prep for best results.

    Examples:

      python main.py research --company "Stripe"

      python main.py research --company "Robinhood" --force
    """
    from agents.company_research import run_research
    run_research(company=company, force=force)


# ---------------------------------------------------------------------------
# signals
# ---------------------------------------------------------------------------

@app.command()
def signals(
    days: int = typer.Option(7, "--days", help="Look-back window in days. Default: 7."),
    min_jobs: int = typer.Option(3, "--min-jobs", help="Minimum postings to count as a surge. Default: 3."),
    serpapi: bool = typer.Option(False, "--serpapi", help="Also search SerpAPI for 'we're hiring' posts (requires SERPAPI_KEY)."),
):
    """Detect companies with a hiring surge based on recent job posting velocity.

    Flags any company that posted 3+ engineering roles in the last 7 days.
    These are high-priority targets — more open roles = more chances to get noticed.

    Examples:

      python main.py signals                       # surge in last 7 days

      python main.py signals --days 14             # wider window

      python main.py signals --min-jobs 2          # lower threshold

      python main.py signals --serpapi             # also check LinkedIn posts
    """
    from agents.hiring_signals import run_signals
    run_signals(days=days, min_jobs=min_jobs, serpapi=serpapi)


# ---------------------------------------------------------------------------
# salary
# ---------------------------------------------------------------------------

@app.command()
def salary(
    company: str = typer.Option(..., "--company", help="Company name to look up."),
    level: str = typer.Option(..., "--level", help="Role level: junior / mid / senior / staff / principal"),
    force: bool = typer.Option(False, "--force", help="Re-fetch even if cached data exists."),
):
    """Look up compensation data for a company and role level from levels.fyi.

    Data is fetched from levels.fyi's public salary endpoint, parsed by Claude
    into a range estimate, and cached in the database for reuse.

    Examples:

      python main.py salary --company "Stripe" --level senior

      python main.py salary --company "Google" --level staff

      python main.py salary --company "Stripe" --level senior --force
    """
    from agents.salary_intel import run_salary
    run_salary(company=company, level=level, force=force)


# ---------------------------------------------------------------------------
# prep
# ---------------------------------------------------------------------------

@prep_app.command("run")
def prep_run(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to generate interview prep for. Must be scored first."),
    force: bool = typer.Option(False, "--force", help="Regenerate even if prep already exists."),
):
    """Generate full interview prep for a job: technical questions, behavioral questions,
    company-specific talking points, and a study plan from gap analysis.

    Requires the job to be scored first: python main.py score --job-id <id>
    Find job IDs with: python main.py jobs

    Examples:

      python main.py prep run --job-id 12

      python main.py prep run --job-id 12 --force
    """
    from agents.interview_prep import run_prep
    run_prep(job_id=job_id, force=force)


@prep_app.command("mock")
def prep_mock(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to run a mock interview for."),
):
    """Run an interactive mock interview session for a job.

    Claude asks questions rotating through technical, behavioral, and company-specific.
    Score each answer 1-10 with specific critique and a suggested stronger answer.
    Session is saved for later review.

    Requires prep to be generated first: python main.py prep run --job-id <id>

    Example:

      python main.py prep mock --job-id 12
    """
    from agents.interview_prep import run_mock
    run_mock(job_id=job_id)


# ---------------------------------------------------------------------------
# referrals
# ---------------------------------------------------------------------------

@app.command()
def referrals(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to find referrals for."),
):
    """Cross-reference your LinkedIn connections against a job's company.

    Export your LinkedIn connections first:
      LinkedIn → Settings → Data Privacy → Get a copy of your data → Connections
      Save the downloaded CSV to: data/linkedin_connections.csv

    Any connections found are saved to the database for outreach.

    Example:

      python main.py referrals --job-id 12
    """
    from agents.referral_detector import run_referrals
    run_referrals(job_id=job_id)


# ---------------------------------------------------------------------------
# outreach
# ---------------------------------------------------------------------------

@app.command()
def outreach(
    job_id: int = typer.Option(None, "--job-id", help="Job ID to generate outreach for."),
    due: bool = typer.Option(False, "--due", help="Show all follow-ups due today across all jobs."),
    send: bool = typer.Option(False, "--send", help="Send via Gmail (requires token.json OAuth setup)."),
    messages: bool = typer.Option(False, "--messages", help="Print the generated message text."),
):
    """Generate personalized outreach messages for a job's contacts, or show follow-ups due.

    Generates both a LinkedIn DM (≤300 chars) and an email for each saved contact.
    Messages are stored in the database. Use --send to send via Gmail if configured.

    Find contacts first with:
      python main.py referrals --job-id <id>      (LinkedIn CSV)
      python main.py find-contacts --job-id <id>   (SerpAPI search)

    Examples:

      python main.py outreach --job-id 12             # generate messages

      python main.py outreach --job-id 12 --messages  # generate and display

      python main.py outreach --job-id 12 --send      # generate and send via Gmail

      python main.py outreach --due                   # show follow-ups due today
    """
    from agents.outreach import run_outreach, run_due_followups
    if due:
        run_due_followups()
    else:
        run_outreach(job_id=job_id, send=send, messages=messages)


# ---------------------------------------------------------------------------
# find-contacts
# ---------------------------------------------------------------------------

@app.command(name="find-contacts")
def find_contacts(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to find contacts for."),
    results: int = typer.Option(5, "--results", help="Max contacts to find per company. Default: 5."),
):
    """Search for recruiters and engineering managers at a job's company via SerpAPI.

    Uses Google to find LinkedIn profiles of recruiters and EMs. Results are saved
    to the database and used by the outreach command to generate messages.

    Requires SERPAPI_KEY in .env. Works best for well-known tech companies.

    Examples:

      python main.py find-contacts --job-id 12

      python main.py find-contacts --job-id 12 --results 10
    """
    from agents.contact_finder import run_contact_finder
    run_contact_finder(job_id=job_id, num_results=results)


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

@app.command()
def apply(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to apply for. Must be scored first."),
    submit: bool = typer.Option(False, "--submit", help="Actually submit the form. Without this flag, fills but does not click submit (safe dry run)."),
):
    """Auto-fill an application form via Playwright (Greenhouse and Lever supported).

    By default runs as a dry run — fills all fields and takes a screenshot
    but does NOT submit. Review the screenshot in data/screenshots/, then
    run with --submit when ready.

    Requires a resume at data/base_resume.pdf (or tailored version from tailor command).
    Cover letter is used automatically if generated for this job.

    Supported ATS: Greenhouse (greenhouse.io), Lever (lever.co)
    Not supported: Workday, LinkedIn Easy Apply (apply manually for these)

    Examples:

      python main.py apply --job-id 12            # dry run — fill + screenshot

      python main.py apply --job-id 12 --submit   # actually submit
    """
    from agents.autofill import run_apply
    run_apply(job_id=job_id, submit=submit)


# ---------------------------------------------------------------------------
# outcome
# ---------------------------------------------------------------------------

@app.command()
def outcome(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to log an interview outcome for."),
):
    """Log an interview outcome for a job (stage reached, rejection reason, feedback).

    Claude analyzes the feedback and suggests study topics to address the gap.
    Outcomes are tracked in the database for analytics.

    Example:

      python main.py outcome --job-id 12
    """
    from agents.analytics import run_outcome
    run_outcome(job_id=job_id)


# ---------------------------------------------------------------------------
# analytics
# ---------------------------------------------------------------------------

@app.command()
def analytics():
    """Show application pipeline analytics and Claude pattern analysis.

    Displays:
      - Pipeline stats (scored, applied, interviews, offers)
      - Outreach response rates
      - Outcome breakdown by fit score range
      - Claude-generated patterns and recommendations (needs 3+ applications)

    Example:

      python main.py analytics
    """
    from agents.analytics import run_analytics
    run_analytics()


# ---------------------------------------------------------------------------
# digest
# ---------------------------------------------------------------------------

@app.command()
def digest():
    """Daily driver command — shows everything you need to act on today.

    Sections:
      - Pipeline summary (applied / interviewing / offers)
      - New scored jobs from the last 24 hours
      - Follow-ups due today
      - Active hiring surges
      - Study plan items from your latest prep session

    Example:

      python main.py digest
    """
    from agents.digest import run_digest
    run_digest()


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# run (orchestrator)
# ---------------------------------------------------------------------------

@app.command()
def run(
    job_id: int = typer.Option(..., "--job-id", help="Job ID to run the full pipeline for. Must be scored first."),
    apply: bool = typer.Option(False, "--apply", help="Also run autofill dry-run at the end (fills form, no submit)."),
    level: str = typer.Option("senior", "--level", help="Role level for salary lookup: junior/mid/senior/staff."),
    force: bool = typer.Option(False, "--force", help="Re-run all steps even if outputs already exist."),
):
    """Run the full pipeline for a job in one command.

    Chains: company research → resume tailor → cover letter → interview prep → salary intel.
    All outputs are cached — re-running is fast if steps already completed.

    Requires the job to be scored first: python main.py score --job-id <id>

    Examples:

      python main.py run --job-id 42                    # full pipeline

      python main.py run --job-id 42 --apply            # also do autofill dry run

      python main.py run --job-id 42 --force            # re-run all steps

      python main.py run --job-id 42 --level staff      # use staff level for salary
    """
    from agents.orchestrator import run_pipeline
    run_pipeline(job_id=job_id, apply=apply, level=level, force=force)


if __name__ == "__main__":
    app()
