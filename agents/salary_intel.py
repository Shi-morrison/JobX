"""Salary Intelligence Agent (Phase 4.2).

Fetches and interprets compensation data from levels.fyi for a given
company and role level. Results are stored in the SalaryData table.

Data flow:
  levels.fyi /salaries.md  →  raw markdown  →  Claude extraction  →  SalaryData DB

Usage:
  python main.py salary --company "Stripe" --level senior
"""

from rich.console import Console
from rich.panel import Panel

from db.session import get_session
from db.models import SalaryData
from tools.llm import ClaudeClient, load_prompt

console = Console()

VALID_LEVELS = ("junior", "mid", "senior", "staff", "principal")


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def get_cached_salary(company_name: str, role_level: str) -> dict | None:
    """Return cached SalaryData for a company+level, or None if not stored."""
    with get_session() as db:
        record = db.query(SalaryData).filter(
            SalaryData.company_name == company_name,
            SalaryData.role_level == role_level,
            SalaryData.source == "levels.fyi",
        ).first()
    return _record_to_dict(record) if record else None


def _record_to_dict(record: SalaryData) -> dict:
    return {
        "company_name": record.company_name,
        "role_level": record.role_level,
        "salary_min": record.salary_min,
        "salary_max": record.salary_max,
        "equity": record.equity or "",
        "source": record.source or "levels.fyi",
        "found": True,
    }


# ---------------------------------------------------------------------------
# Core fetch function
# ---------------------------------------------------------------------------

def fetch_salary_data(
    company_name: str,
    role_level: str,
    force: bool = False,
) -> dict:
    """Fetch and store comp data for a company + role level.

    Steps:
      1. Check DB cache (skip if force=True).
      2. Pull levels.fyi compensation markdown.
      3. Send raw data to Claude to extract role-level-specific ranges.
      4. Store in SalaryData table and return.

    Returns a dict with salary_min, salary_max, equity, notes, and found flag.
    """
    role_level = role_level.lower().strip()
    if role_level not in VALID_LEVELS:
        console.print(
            f"[yellow]Unknown level '{role_level}'. "
            f"Valid: {', '.join(VALID_LEVELS)}[/yellow]"
        )

    # Cache check
    if not force:
        cached = get_cached_salary(company_name, role_level)
        if cached:
            console.print(f"[dim]Using cached salary data for {company_name} ({role_level}).[/dim]")
            return cached

    console.print(f"\n[bold]Salary Intel:[/bold] {company_name} — {role_level}\n")

    # Step 1: levels.fyi
    comp = {}
    with console.status("[1/2] Fetching compensation data from levels.fyi..."):
        try:
            from tools.levelsfyi import fetch_levelsfyi_compensation
            comp = fetch_levelsfyi_compensation(company_name)
            if comp.get("found"):
                median = comp.get("median_total_comp", "—")
                console.print(f"  [green]✓[/green] Found. Median total comp: {median}")
            else:
                console.print(
                    f"  [dim]✗ No data found for {company_name} on levels.fyi[/dim]"
                )
        except Exception as e:
            console.print(f"  [yellow]Warning: {e}[/yellow]")

    if not comp.get("found"):
        return {
            "company_name": company_name,
            "role_level": role_level,
            "salary_min": None,
            "salary_max": None,
            "equity": "",
            "source": "levels.fyi",
            "found": False,
            "note": "No compensation data found on levels.fyi for this company.",
        }

    # Step 2: Claude extraction
    extracted = {}
    with console.status("[2/2] Extracting role-level ranges with Claude..."):
        try:
            families = comp.get("job_families", [])
            families_text = "\n".join(
                f"- {f['role']}: {f['median']}" for f in families
            ) or "No role breakdown available."

            prompt = load_prompt(
                "salary_intel",
                company=company_name,
                role_level=role_level,
                median_total_comp=comp.get("median_total_comp", "Unknown"),
                software_engineer_median=comp.get("software_engineer_median", "Unknown"),
                job_families=families_text,
                raw_summary=comp.get("raw_summary", ""),
            )
            client = ClaudeClient()
            extracted = client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            console.print(
                f"  [green]✓[/green] Matched: {extracted.get('matched_role', '—')}"
            )
        except Exception as e:
            console.print(f"  [yellow]Warning: Claude extraction failed: {e}[/yellow]")

    salary_min = extracted.get("salary_min")
    salary_max = extracted.get("salary_max")
    equity = extracted.get("equity_range", "")
    notes = extracted.get("notes", "")
    matched_role = extracted.get("matched_role", "")

    # Persist
    with get_session() as db:
        record = db.query(SalaryData).filter(
            SalaryData.company_name == company_name,
            SalaryData.role_level == role_level,
            SalaryData.source == "levels.fyi",
        ).first()
        if not record:
            record = SalaryData(
                company_name=company_name,
                role_level=role_level,
                source="levels.fyi",
            )
            db.add(record)
        record.salary_min = salary_min
        record.salary_max = salary_max
        record.equity = equity

    return {
        "company_name": company_name,
        "role_level": role_level,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "equity": equity,
        "notes": notes,
        "matched_role": matched_role,
        "source": "levels.fyi",
        "found": True,
        "all_levels": comp.get("job_families", []),
        "median_total_comp": comp.get("median_total_comp", ""),
    }


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _fmt_salary(val: int | None) -> str:
    if val is None:
        return "—"
    return f"${val:,}"


def _print_salary_report(result: dict) -> None:
    lines = []

    lo = _fmt_salary(result.get("salary_min"))
    hi = _fmt_salary(result.get("salary_max"))

    if result.get("salary_min") or result.get("salary_max"):
        lines.append(f"[bold]Total comp range:[/bold]  {lo} – {hi}  (estimated)")
    elif result.get("median_total_comp"):
        lines.append(
            f"[bold]Median total comp (all levels):[/bold]  {result['median_total_comp']}"
        )

    if result.get("matched_role"):
        lines.append(f"[bold]Based on:[/bold]  {result['matched_role']}")

    if result.get("equity"):
        lines.append(f"[bold]Equity / bonus:[/bold]  {result['equity']}")

    if result.get("notes"):
        lines.append(f"\n[dim]{result['notes']}[/dim]")

    all_levels = result.get("all_levels", [])
    if all_levels:
        lines.append("\n[bold]All role families on levels.fyi:[/bold]")
        for fam in all_levels[:12]:
            lines.append(f"  • {fam['role']}: {fam['median']}")

    lines.append(
        f"\n[dim]Source: levels.fyi  |  Cached in DB for future use[/dim]"
    )

    console.print()
    console.print(Panel(
        "\n".join(lines),
        title=f"[bold]{result['company_name']}[/bold] — {result['role_level'].capitalize()} Compensation",
        border_style="green",
    ))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_salary(company: str, level: str, force: bool = False) -> None:
    """CLI entry point for: python main.py salary --company "Stripe" --level senior"""
    result = fetch_salary_data(company, level, force=force)
    if not result.get("found"):
        console.print(
            f"[yellow]No salary data found for {company} on levels.fyi.[/yellow]"
        )
        console.print(
            "[dim]levels.fyi may not have comp data for this company. "
            "It works best for well-known tech companies.[/dim]"
        )
        return
    _print_salary_report(result)
