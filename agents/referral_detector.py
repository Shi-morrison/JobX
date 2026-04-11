"""Referral Detector (Phase 5.1).

Cross-references a LinkedIn connections CSV export against a job's company
to find warm contacts the user can reach out to directly.

How to export LinkedIn connections:
  LinkedIn → Settings → Data Privacy → Get a copy of your data → Connections
  Download and save to: data/linkedin_connections.csv

CSV format (LinkedIn export):
  First Name,Last Name,URL,Email Address,Company,Position,Connected On
"""

import csv
from pathlib import Path

from rich.console import Console
from rich.table import Table

from db.session import get_session
from db.models import Job, Contact

console = Console()

CONNECTIONS_CSV = Path("data/linkedin_connections.csv")


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def load_connections(csv_path: Path = CONNECTIONS_CSV) -> list[dict]:
    """Parse LinkedIn connections CSV export into a list of dicts.

    Handles the LinkedIn export format which has 3 header rows (notes, blank, headers).

    Returns:
        List of dicts with keys: first_name, last_name, name, url, email, company, position
    """
    if not csv_path.exists():
        return []

    connections = []
    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            # LinkedIn CSVs have 3 lines before the real headers:
            # line 0: "Notes:" or similar metadata
            # line 1: blank
            # line 2: actual column headers
            # Try to auto-detect which line is the real header.
            raw = f.read()

        lines = raw.splitlines()
        header_idx = 0
        for i, line in enumerate(lines):
            if "First Name" in line or "first_name" in line.lower():
                header_idx = i
                break

        data_lines = "\n".join(lines[header_idx:])
        reader = csv.DictReader(data_lines.splitlines())

        for row in reader:
            # Normalize keys (LinkedIn uses "First Name" with spaces)
            normalized = {k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in row.items()}
            first = normalized.get("first_name", "")
            last = normalized.get("last_name", "")
            connections.append({
                "first_name": first,
                "last_name": last,
                "name": f"{first} {last}".strip(),
                "url": normalized.get("url", ""),
                "email": normalized.get("email_address", ""),
                "company": normalized.get("company", ""),
                "position": normalized.get("position", ""),
            })
    except Exception as e:
        console.print(f"[yellow]Warning: could not parse connections CSV: {e}[/yellow]")

    return connections


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    """Lowercase and strip for fuzzy company name matching."""
    return s.lower().strip().replace(",", "").replace(".", "").replace("inc", "").replace("llc", "").strip()


def find_referrals(job_company: str, connections: list[dict]) -> list[dict]:
    """Return connections whose company matches job_company (fuzzy)."""
    target = _normalize(job_company)
    matches = []
    for conn in connections:
        conn_company = _normalize(conn.get("company", ""))
        if not conn_company:
            continue
        # Match if either contains the other (handles "Stripe" vs "Stripe, Inc.")
        if target in conn_company or conn_company in target:
            matches.append(conn)
    return matches


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def save_referrals_to_db(job_id: int, matches: list[dict]) -> list[Contact]:
    """Upsert referral contacts into the Contact table."""
    saved = []
    with get_session() as db:
        for match in matches:
            existing = db.query(Contact).filter(
                Contact.job_id == job_id,
                Contact.linkedin_url == match["url"],
            ).first()
            if existing:
                saved.append(existing)
                continue
            contact = Contact(
                job_id=job_id,
                name=match["name"],
                title=match["position"],
                linkedin_url=match["url"],
                email=match["email"],
                company=match["company"],
            )
            db.add(contact)
            saved.append(contact)
    return saved


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_referrals(job_id: int) -> list[dict]:
    """CLI entry point: python main.py referrals --job-id <id>

    Returns the list of matched connections.
    """
    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        console.print(f"[red]No job found with ID {job_id}.[/red]")
        return []

    if not CONNECTIONS_CSV.exists():
        console.print(f"[yellow]LinkedIn connections CSV not found at {CONNECTIONS_CSV}[/yellow]")
        console.print("[dim]Export your LinkedIn connections:[/dim]")
        console.print("  LinkedIn → Settings → Data Privacy → Get a copy of your data → Connections")
        console.print(f"  Save the downloaded CSV to: [bold]{CONNECTIONS_CSV}[/bold]")
        return []

    console.print(f"\n[bold]Referral Detector:[/bold] {job.title} @ {job.company}\n")

    connections = load_connections()
    console.print(f"[dim]Loaded {len(connections)} LinkedIn connections.[/dim]")

    matches = find_referrals(job.company, connections)

    if not matches:
        console.print(
            f"[yellow]No connections found at {job.company}.[/yellow]\n"
            f"[dim]Try contact finder: python main.py outreach --job-id {job_id}[/dim]"
        )
        return []

    save_referrals_to_db(job_id, matches)

    table = Table(
        title=f"[green]{len(matches)} Connection(s) at {job.company}[/green]",
        show_lines=True,
    )
    table.add_column("Name", style="bold")
    table.add_column("Title / Position")
    table.add_column("LinkedIn")
    table.add_column("Email")

    for m in matches:
        table.add_row(
            m["name"],
            m["position"] or "—",
            m["url"] or "—",
            m["email"] or "—",
        )

    console.print(table)
    console.print(
        f"\n[dim]Contacts saved. Generate outreach: "
        f"python main.py outreach --job-id {job_id}[/dim]"
    )
    return matches
