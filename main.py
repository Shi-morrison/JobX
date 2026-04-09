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
        help="Location to search (e.g. 'Remote', 'New York', 'San Francisco'). Overrides TARGET_LOCATIONS in .env for this run.",
    ),
    level: str = typer.Option(
        None,
        "--level",
        help="Seniority level to filter for: intern, junior, mid, senior, staff. Appended to each search term.",
    ),
    job_type: str = typer.Option(
        None,
        "--job-type",
        help="Work arrangement: remote, hybrid, onsite. Filters results accordingly.",
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

      python main.py search --location Remote --level senior

      python main.py search --hours-back 48 --job-type remote --results 20
    """
    from tools.scraper import run_scraper
    run_scraper(
        hours_back=hours_back,
        location_override=location,
        level=level,
        job_type=job_type,
        results_per_query=results,
    )


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------

@app.command()
def score():
    """Score and rank all unscored jobs."""
    console.print("[yellow]Score command — coming in Phase 2.[/yellow]")


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
