"""Contact Finder (Phase 5.2).

Finds recruiters and engineering managers at a target company using SerpAPI.
Extracts contact details from search snippets, stores in Contact table.

Note: Playwright scraping of LinkedIn profiles is not implemented — LinkedIn
aggressively blocks automated access. Instead we surface the LinkedIn URL
so the user can visit the profile and reach out directly or via LinkedIn.
"""

from rich.console import Console
from rich.table import Table

from db.session import get_session
from db.models import Job, Contact

console = Console()

# Search queries to find relevant contacts
_SEARCH_QUERIES = [
    'site:linkedin.com/in "{company}" recruiter software engineer',
    'site:linkedin.com/in "{company}" "engineering manager"',
    'site:linkedin.com/in "{company}" "technical recruiter"',
]


# ---------------------------------------------------------------------------
# SerpAPI search
# ---------------------------------------------------------------------------

def search_contacts(company: str, num_results: int = 5) -> list[dict]:
    """Search LinkedIn profiles for recruiters/EMs at a company via SerpAPI.

    Returns:
        List of raw contact candidates: {name, title, linkedin_url, snippet}
    """
    try:
        from tools.search import search_web
    except ImportError:
        return []

    found: list[dict] = []
    seen_urls: set[str] = set()

    for query_template in _SEARCH_QUERIES:
        query = query_template.replace("{company}", company)
        results = search_web(query, num_results=num_results)
        for r in results:
            url = r.get("url", "")
            if "linkedin.com/in/" not in url or url in seen_urls:
                continue
            seen_urls.add(url)
            name, title = _parse_name_title(r.get("title", ""), company)
            found.append({
                "name": name,
                "title": title,
                "linkedin_url": url,
                "snippet": r.get("snippet", ""),
                "company": company,
            })
        if len(found) >= num_results:
            break

    return found[:num_results]


def _parse_name_title(search_title: str, company: str) -> tuple[str, str]:
    """Extract name and job title from a Google search result title.

    LinkedIn titles typically look like:
      "Jane Doe - Recruiter at Stripe | LinkedIn"
      "John Smith - Engineering Manager | LinkedIn"
    """
    # Strip " | LinkedIn" and similar suffixes
    for suffix in [" | LinkedIn", " - LinkedIn", " · LinkedIn"]:
        if suffix in search_title:
            search_title = search_title.split(suffix)[0].strip()

    if " - " in search_title:
        parts = search_title.split(" - ", 1)
        name = parts[0].strip()
        # Title may include "at Company" — strip that part
        title_raw = parts[1].strip()
        for sep in [f" at {company}", " at "]:
            if sep.lower() in title_raw.lower():
                title_raw = title_raw[:title_raw.lower().index(sep.lower())].strip()
        return name, title_raw

    # Fallback: whole string is name
    return search_title.strip(), ""


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def save_contacts(job_id: int, candidates: list[dict]) -> list[Contact]:
    """Upsert contact candidates into the Contact table. Return saved records."""
    saved = []
    with get_session() as db:
        for c in candidates:
            existing = db.query(Contact).filter(
                Contact.job_id == job_id,
                Contact.linkedin_url == c["linkedin_url"],
            ).first()
            if existing:
                saved.append(existing)
                continue
            contact = Contact(
                job_id=job_id,
                name=c.get("name", ""),
                title=c.get("title", ""),
                linkedin_url=c.get("linkedin_url", ""),
                email="",
                company=c.get("company", ""),
            )
            db.add(contact)
            saved.append(contact)
    return saved


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_contact_finder(job_id: int, num_results: int = 5) -> list[dict]:
    """Find contacts for a job's company. Returns list of found candidates."""
    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        console.print(f"[red]No job found with ID {job_id}.[/red]")
        return []

    from config import settings
    if not settings.serpapi_key:
        console.print(
            "[yellow]SERPAPI_KEY not configured — contact finder requires SerpAPI.[/yellow]"
        )
        console.print("[dim]Add SERPAPI_KEY to .env to enable contact search.[/dim]")
        return []

    console.print(f"\n[bold]Contact Finder:[/bold] {job.title} @ {job.company}\n")

    candidates = []
    with console.status(f"Searching LinkedIn profiles for {job.company} contacts..."):
        candidates = search_contacts(job.company, num_results=num_results)

    if not candidates:
        console.print(
            f"[yellow]No contacts found for {job.company} via SerpAPI.[/yellow]"
        )
        return []

    save_contacts(job_id, candidates)

    table = Table(
        title=f"[green]{len(candidates)} Contact(s) found at {job.company}[/green]",
        show_lines=True,
    )
    table.add_column("Name", style="bold")
    table.add_column("Title")
    table.add_column("LinkedIn URL")

    for c in candidates:
        table.add_row(c["name"] or "—", c["title"] or "—", c["linkedin_url"])

    console.print(table)
    console.print(
        f"\n[dim]Contacts saved. Generate outreach messages: "
        f"python main.py outreach --job-id {job_id} --messages[/dim]"
    )
    return candidates
