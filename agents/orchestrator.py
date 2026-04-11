"""Orchestrator — chains the full pipeline for a single job in one command.

  python main.py run --job-id 42

Steps:
  1. Research company (skip if cached)
  2. Tailor resume
  3. Generate cover letter
  4. Generate interview prep
  5. Fetch salary intel
  6. Auto-apply dry run (optional, requires --apply flag)

Each step is skipped gracefully if it fails or if prerequisites are missing.
Results are printed as a summary panel at the end.
"""

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from db.session import get_session
from db.models import Job

console = Console()


def run_pipeline(
    job_id: int,
    apply: bool = False,
    level: str = "senior",
    force: bool = False,
) -> None:
    """Run the full pipeline for a single job.

    Args:
        job_id: The job to process.
        apply:  If True, also run autofill dry-run at the end.
        level:  Role level for salary lookup (junior/mid/senior/staff).
        force:  Re-run steps even if outputs already exist.
    """
    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        console.print(f"[red]No job found with ID {job_id}.[/red]")
        return

    if not job.fit_score:
        console.print(
            f"[yellow]Job {job_id} has not been scored yet.[/yellow]\n"
            f"[dim]Score it first: python main.py score --job-id {job_id}[/dim]"
        )
        return

    score_color = "green" if job.fit_score >= 7 else "yellow" if job.fit_score >= 5 else "red"
    console.print()
    console.print(Panel(
        f"[bold]{job.title}[/bold] @ {job.company}\n"
        f"Fit score: [{score_color}]{job.fit_score}/10[/{score_color}]   "
        f"Job ID: {job_id}",
        title="[bold]JobX Orchestrator[/bold]",
        border_style="blue",
    ))
    console.print()

    results = {}

    # ------------------------------------------------------------------
    # Step 1 — Company research
    # ------------------------------------------------------------------
    console.print(Rule("[bold]Step 1 / 5 — Company Research[/bold]"))
    try:
        from agents.company_research import research_company, get_cached_research
        cached = get_cached_research(job.company)
        if cached and not force:
            console.print(f"[dim]✓ Using cached research for {job.company}.[/dim]")
            results["research"] = "cached"
        else:
            research_company(job.company, force=force)
            results["research"] = "done"
    except Exception as e:
        console.print(f"[yellow]Research skipped: {e}[/yellow]")
        results["research"] = "skipped"
    console.print()

    # ------------------------------------------------------------------
    # Step 2 — Resume tailor
    # ------------------------------------------------------------------
    console.print(Rule("[bold]Step 2 / 5 — Resume Tailor[/bold]"))
    try:
        from pathlib import Path
        tailored = Path(f"data/resume_versions/resume_{job_id}.docx")
        if tailored.exists() and not force:
            console.print(f"[dim]✓ Tailored resume already exists: {tailored}[/dim]")
            results["tailor"] = "cached"
        else:
            from agents.resume_tailor import run_tailor
            run_tailor(job_id=job_id)
            results["tailor"] = "done"
    except Exception as e:
        console.print(f"[yellow]Resume tailor skipped: {e}[/yellow]")
        results["tailor"] = "skipped"
    console.print()

    # ------------------------------------------------------------------
    # Step 3 — Cover letter
    # ------------------------------------------------------------------
    console.print(Rule("[bold]Step 3 / 5 — Cover Letter[/bold]"))
    try:
        from pathlib import Path
        cl = Path(f"data/cover_letters/cover_letter_{job_id}.docx")
        if cl.exists() and not force:
            console.print(f"[dim]✓ Cover letter already exists: {cl}[/dim]")
            results["cover_letter"] = "cached"
        else:
            from agents.cover_letter import run_cover_letter
            run_cover_letter(job_id=job_id)
            results["cover_letter"] = "done"
    except Exception as e:
        console.print(f"[yellow]Cover letter skipped: {e}[/yellow]")
        results["cover_letter"] = "skipped"
    console.print()

    # ------------------------------------------------------------------
    # Step 4 — Interview prep
    # ------------------------------------------------------------------
    console.print(Rule("[bold]Step 4 / 5 — Interview Prep[/bold]"))
    try:
        from agents.interview_prep import run_prep
        run_prep(job_id=job_id, force=force)
        results["prep"] = "done"
    except Exception as e:
        console.print(f"[yellow]Interview prep skipped: {e}[/yellow]")
        results["prep"] = "skipped"
    console.print()

    # ------------------------------------------------------------------
    # Step 5 — Salary intel
    # ------------------------------------------------------------------
    console.print(Rule("[bold]Step 5 / 5 — Salary Intel[/bold]"))
    try:
        from agents.salary_intel import fetch_salary_data, _print_salary_report
        salary = fetch_salary_data(job.company, level, force=force)
        if salary.get("found"):
            _print_salary_report(salary)
            results["salary"] = f"{salary.get('salary_min', '?')}–{salary.get('salary_max', '?')}"
        else:
            console.print(f"[dim]No salary data found for {job.company} on levels.fyi.[/dim]")
            results["salary"] = "not found"
    except Exception as e:
        console.print(f"[yellow]Salary intel skipped: {e}[/yellow]")
        results["salary"] = "skipped"
    console.print()

    # ------------------------------------------------------------------
    # Optional: autofill dry run
    # ------------------------------------------------------------------
    if apply:
        console.print(Rule("[bold]Bonus — Autofill Dry Run[/bold]"))
        try:
            from agents.autofill import run_apply
            run_apply(job_id=job_id, submit=False)
            results["autofill"] = "dry run complete"
        except Exception as e:
            console.print(f"[yellow]Autofill skipped: {e}[/yellow]")
            results["autofill"] = "skipped"
        console.print()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    icon = {"done": "[green]✓[/green]", "cached": "[dim]✓ (cached)[/dim]", "skipped": "[yellow]✗ skipped[/yellow]", "not found": "[dim]— not found[/dim]"}
    lines = [
        f"  Research:      {icon.get(results.get('research',''), results.get('research',''))}",
        f"  Resume tailor: {icon.get(results.get('tailor',''), results.get('tailor',''))}",
        f"  Cover letter:  {icon.get(results.get('cover_letter',''), results.get('cover_letter',''))}",
        f"  Prep:          {icon.get(results.get('prep',''), results.get('prep',''))}",
        f"  Salary:        {icon.get(results.get('salary',''), results.get('salary',''))}",
    ]
    if apply:
        lines.append(f"  Autofill:      {icon.get(results.get('autofill',''), results.get('autofill',''))}")

    lines += [
        "",
        f"  [dim]Review tailored resume:  data/resume_versions/resume_{job_id}.docx[/dim]",
        f"  [dim]Review cover letter:     data/cover_letters/cover_letter_{job_id}.docx[/dim]",
    ]
    if apply:
        lines.append(f"  [dim]Review screenshot:       data/screenshots/[/dim]")
    lines += [
        "",
        f"  [dim]To submit: python main.py apply --job-id {job_id} --submit[/dim]",
        f"  [dim]Mock interview: python main.py prep mock --job-id {job_id}[/dim]",
    ]

    console.print(Panel(
        "\n".join(lines),
        title=f"[bold]Pipeline Complete — {job.title} @ {job.company}[/bold]",
        border_style="green",
    ))
