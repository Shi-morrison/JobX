import json
import re
import time
import random
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

_LEVEL_KEYWORDS = {
    "intern": "Intern",
    "junior": "Junior",
    "mid": "Mid-level",
    "senior": "Senior",
    "staff": "Staff",
}


def _clean_str(value) -> str:
    """Convert a scraped field to a clean string, returning empty string for missing/NaN values.

    JobSpy uses pandas internally — missing fields come back as float('nan'), which is
    truthy in Python, so `str(nan or "")` produces the literal string "nan" instead of "".
    """
    if value is None:
        return ""
    try:
        import math
        if isinstance(value, float) and math.isnan(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


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


def _normalize_location(location: str) -> str:
    """Normalize location string — 'remote' / 'REMOTE' all become 'Remote'."""
    if location.strip().lower() == "remote":
        return "Remote"
    return location.strip().title()


# ---------------------------------------------------------------------------
# Core scrape logic
# ---------------------------------------------------------------------------

def _scrape_one(
    role: str,
    location: str,
    hours_old: int,
    results_per_query: int = 15,
) -> list[dict]:
    """Scrape one role+location combo. Returns a list of job dicts.

    If location is 'Remote', passes is_remote=True to JobSpy for a tighter filter.
    """
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
        "linkedin_fetch_description": True,
    }
    if location == "Remote":
        kwargs["is_remote"] = True

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
            "description": _clean_str(row.get("description")),
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
# Description backfill (for jobs scraped before linkedin_fetch_description)
# ---------------------------------------------------------------------------

_LINKEDIN_JOB_API = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_linkedin_job_id(url: str) -> str | None:
    """Extract numeric job ID from a LinkedIn job URL."""
    match = re.search(r"/(\d{10,})", url)
    return match.group(1) if match else None


def _fetch_linkedin_description(url: str) -> str:
    """Fetch the description for a single LinkedIn job URL.

    Uses LinkedIn's public jobs-guest API (no auth required).
    Returns empty string on failure.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return ""

    job_id = _extract_linkedin_job_id(url)
    if not job_id:
        return ""

    api_url = _LINKEDIN_JOB_API.format(job_id=job_id)
    try:
        resp = requests.get(api_url, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        desc_div = soup.find("div", class_="description__text")
        if desc_div:
            return desc_div.get_text(separator="\n").strip()
        # Fallback: grab any show-more-less-html block
        fallback = soup.find("div", class_=re.compile(r"show-more-less-html"))
        if fallback:
            return fallback.get_text(separator="\n").strip()
    except Exception:
        pass
    return ""


def run_fetch_descriptions(limit: int | None = None) -> None:
    """Backfill descriptions for jobs that were scraped without one.

    Only processes LinkedIn jobs (Indeed descriptions are always present).
    Adds a small random delay between requests to avoid rate limiting.
    """
    with get_session() as db:
        query = db.query(Job).filter(
            Job.source == "linkedin",
            Job.fit_score.is_(None),
            (Job.description.is_(None) | (Job.description == "") | (Job.description == "nan")),
        )
        if limit is not None:
            query = query.limit(limit)
        jobs = query.all()

    if not jobs:
        console.print("[yellow]No LinkedIn jobs missing descriptions.[/yellow]")
        return

    console.print(f"[dim]Fetching descriptions for {len(jobs)} LinkedIn jobs...[/dim]")
    updated = 0
    failed = 0

    with get_session() as db:
        for i, job in enumerate(jobs, 1):
            console.print(f"  [{i}/{len(jobs)}] {job.title} @ {job.company}...", end=" ")
            desc = _fetch_linkedin_description(job.url)
            if desc:
                db_job = db.query(Job).filter(Job.id == job.id).first()
                if db_job:
                    db_job.description = desc
                console.print("[green]✓[/green]")
                updated += 1
            else:
                console.print("[red]✗ no description found[/red]")
                failed += 1

            # Polite delay: 1–3 seconds between requests
            if i < len(jobs):
                time.sleep(random.uniform(1.0, 3.0))

    console.print(f"\n[green]Updated {updated} jobs.[/green] {failed} could not be fetched.")
    if updated:
        console.print("[dim]Run [bold]python main.py score[/bold] to score the newly described jobs.[/dim]")


# ---------------------------------------------------------------------------
# Public entry point called by main.py
# ---------------------------------------------------------------------------

def run_scraper(
    hours_back: int | None = None,
    location_override: str | None = None,
    level: str | None = None,
    results_per_query: int = 15,
) -> None:
    """Scrape new job listings and store them in the database.

    Args:
        hours_back: How far back to look. Auto-calculates from last run if None (default 24h).
        location_override: Single location overriding TARGET_LOCATIONS in .env.
                           Case-insensitive — 'remote', 'Remote', 'REMOTE' all work.
        level: Seniority level — intern/junior/mid/senior/staff. Prepended to each search term.
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
            hours_old = max(int(hours_since) + 1, 24)
            console.print(f"[dim]Last scraped {hours_since:.1f}h ago — fetching listings from the last {hours_old}h.[/dim]")
        else:
            hours_old = 24
            console.print("[dim]First run — fetching listings from the last 24 hours.[/dim]")

    # Build search terms — prepend level keyword if provided
    base_roles = settings.target_roles
    if level:
        level_word = _LEVEL_KEYWORDS.get(level.lower(), level.capitalize())
        roles = [f"{level_word} {role}" for role in base_roles]
        console.print(f"[dim]Level filter: [bold]{level_word}[/bold][/dim]")
    else:
        roles = base_roles

    # Normalize locations — user can type 'remote', 'Remote', or 'REMOTE'
    if location_override:
        locations = [_normalize_location(location_override)]
    else:
        locations = [_normalize_location(loc) for loc in settings.target_locations]

    console.print(f"[dim]Locations: {', '.join(locations)}[/dim]")

    all_jobs: list[dict] = []
    with console.status(f"Scraping {len(roles)} roles × {len(locations)} locations via LinkedIn & Indeed..."):
        for role in roles:
            for location in locations:
                raw = _scrape_one(role, location, hours_old, results_per_query=results_per_query)
                all_jobs.extend(raw)

    console.print(f"[dim]Fetched {len(all_jobs)} raw listings. Deduplicating...[/dim]")

    new_jobs = _insert_new_jobs(all_jobs)

    if all_jobs is not None:
        state["last_scraped_at"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

    _print_results(new_jobs)
