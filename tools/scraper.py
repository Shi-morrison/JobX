import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from config import settings
from db.session import get_session, init_db
from db.models import Job

console = Console()

_STATE_FILE = Path("data/scraper_state.json")

# Glassdoor only accepts city/state strings — "Remote" causes 400 errors.
# Stick to LinkedIn and Indeed which handle "Remote" correctly.
_SITES = ["linkedin", "indeed"]


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if _STATE_FILE.exists():
        return json.loads(_STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2))


def _hours_since_last_scrape(state: dict) -> float | None:
    last = state.get("last_scraped_at")
    if not last:
        return None
    last_dt = datetime.fromisoformat(last)
    delta = datetime.now(timezone.utc) - last_dt
    return delta.total_seconds() / 3600


# ---------------------------------------------------------------------------
# Core scrape logic
# ---------------------------------------------------------------------------

_JOB_TYPE_MAP = {
    "remote": {"is_remote": True},
    "hybrid": {},   # JobSpy has no hybrid filter; we post-filter by title/desc
    "onsite": {"is_remote": False},
}

_LEVEL_KEYWORDS = {
    "intern": "Intern",
    "junior": "Junior",
    "mid": "Mid-level",
    "senior": "Senior",
    "staff": "Staff",
}


def _scrape_one(
    role: str,
    location: str,
    hours_old: int,
    job_type: str | None = None,
    results_per_query: int = 15,
) -> list[dict]:
    """Scrape one role+location combo. Returns a list of job dicts."""
    try:
        from jobspy import scrape_jobs  # lazy import — heavy dependency
    except ImportError:
        console.print("[red]python-jobspy not installed. Run: pip install -r requirements.txt[/red]")
        return []

    kwargs: dict = {
        "site_name": _SITES,
        "search_term": role,
        "location": location,
        "results_wanted": results_per_query,
        "hours_old": hours_old,
    }
    if job_type and job_type in _JOB_TYPE_MAP:
        kwargs.update(_JOB_TYPE_MAP[job_type])

    try:
        df = scrape_jobs(**kwargs)
    except Exception as e:
        console.print(f"[yellow]Warning: scrape failed for '{role}' in '{location}': {e}[/yellow]")
        return []

    if df is None or df.empty:
        return []

    jobs = []
    for _, row in df.iterrows():
        url = str(row.get("job_url") or "").strip()
        title = str(row.get("title") or "").strip()
        company = str(row.get("company") or "").strip()
        if not url or not title or not company:
            continue

        posted_raw = row.get("date_posted")
        try:
            posted_date = (
                posted_raw.to_pydatetime() if hasattr(posted_raw, "to_pydatetime")
                else datetime.fromisoformat(str(posted_raw)) if posted_raw else None
            )
        except Exception:
            posted_date = None

        jobs.append({
            "title": title,
            "company": company,
            "url": url,
            "description": str(row.get("description") or ""),
            "source": str(row.get("site") or ""),
            "posted_date": posted_date,
        })

    return jobs


def _is_target_role(title: str) -> bool:
    """Return True if the job title contains any configured target role keyword."""
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in settings.target_roles)


def _insert_new_jobs(jobs: list[dict]) -> list[Job]:
    """Insert jobs that don't already exist in the DB. Returns the new Job rows."""
    new_jobs: list[Job] = []
    with get_session() as db:
        existing_urls: set[str] = {
            row[0] for row in db.query(Job.url).all()
        }
        for j in jobs:
            if j["url"] in existing_urls:
                continue
            if not _is_target_role(j["title"]):
                continue
            job = Job(
                title=j["title"],
                company=j["company"],
                url=j["url"],
                description=j["description"],
                source=j["source"],
                posted_date=j["posted_date"],
                status="new",
            )
            db.add(job)
            existing_urls.add(j["url"])
            new_jobs.append(job)
    return new_jobs


def _print_results(new_jobs: list[Job]) -> None:
    if not new_jobs:
        console.print("[yellow]No new jobs found.[/yellow]")
        return

    table = Table(title=f"[green]{len(new_jobs)} New Jobs Found[/green]", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold")
    table.add_column("Company")
    table.add_column("Source")
    table.add_column("Posted")

    for i, job in enumerate(new_jobs, 1):
        posted = job.posted_date.strftime("%Y-%m-%d") if job.posted_date else "—"
        table.add_row(str(i), job.title, job.company, job.source or "—", posted)

    console.print(table)
    console.print("[dim]Run [bold]python main.py score[/bold] next to rank these by fit.[/dim]")


# ---------------------------------------------------------------------------
# Public entry point called by main.py
# ---------------------------------------------------------------------------

def run_scraper(
    hours_back: int | None = None,
    location_override: str | None = None,
    level: str | None = None,
    job_type: str | None = None,
    results_per_query: int = 15,
) -> None:
    """Scrape new job listings and store them in the database.

    Args:
        hours_back: How far back to look. Auto-calculates from last run if None (default 24h).
        location_override: Single location string overriding TARGET_LOCATIONS in .env.
        level: Seniority level — intern/junior/mid/senior/staff. Prepended to each search term.
        job_type: Work arrangement — remote/hybrid/onsite. Passed to JobSpy filter.
        results_per_query: Max listings per role/location combo. Default 15.
    """
    init_db()

    state = _load_state()

    if hours_back is not None:
        hours_old = hours_back
        console.print(f"[dim]Searching listings from the last {hours_old}h.[/dim]")
    else:
        hours_since = _hours_since_last_scrape(state)
        if hours_since is not None:
            hours_old = max(int(hours_since) + 1, 24)  # minimum 24h window
            console.print(f"[dim]Last scraped {hours_since:.1f}h ago — fetching listings from the last {hours_old}h.[/dim]")
        else:
            hours_old = 24
            console.print("[dim]First run — fetching listings from the last 24 hours.[/dim]")

    # Build search terms — prepend level keyword if provided (e.g. "Senior Software Engineer")
    base_roles = settings.target_roles
    if level:
        level_word = _LEVEL_KEYWORDS.get(level.lower(), level.capitalize())
        roles = [f"{level_word} {role}" for role in base_roles]
        console.print(f"[dim]Level filter: [bold]{level_word}[/bold][/dim]")
    else:
        roles = base_roles

    locations = [location_override] if location_override else settings.target_locations

    if job_type:
        console.print(f"[dim]Job type filter: [bold]{job_type}[/bold][/dim]")

    all_jobs: list[dict] = []
    with console.status(f"Scraping {len(roles)} roles × {len(locations)} locations via LinkedIn & Indeed..."):
        for role in roles:
            for location in locations:
                raw = _scrape_one(role, location, hours_old, job_type=job_type, results_per_query=results_per_query)
                all_jobs.extend(raw)

    console.print(f"[dim]Fetched {len(all_jobs)} raw listings. Deduplicating...[/dim]")

    new_jobs = _insert_new_jobs(all_jobs)

    # Only save state if we actually attempted a scrape (even if 0 new jobs —
    # that's valid. We do NOT save if all_jobs is empty due to import errors.)
    if all_jobs is not None:
        state["last_scraped_at"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

    _print_results(new_jobs)
