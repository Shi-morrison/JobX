"""Auto-Application Agent (Phase 6).

Detects the ATS type from a job URL, fills the application form using
Playwright, and logs the result to the Application table.

Supported ATS:
  - Greenhouse  (boards.greenhouse.io / job-boards.greenhouse.io)
  - Lever       (jobs.lever.co)

Unsupported (too brittle / login-walled):
  - Workday     — custom per-company, frequent DOM changes
  - LinkedIn Easy Apply — requires LinkedIn session management

Usage:
  python main.py apply --job-id 12          # dry run — fills but doesn't submit
  python main.py apply --job-id 12 --submit # actually submits
"""

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from db.session import get_session
from db.models import Job, Application, ResumeVersion
from tools.llm import parse_resume
from agents.scorer import _build_experience_summary

console = Console()


# ---------------------------------------------------------------------------
# ATS detection
# ---------------------------------------------------------------------------

def detect_ats(url: str) -> str | None:
    """Return ATS type string from a job URL, or None if unsupported.

    Returns: "greenhouse" | "lever" | "workday" | "linkedin" | None
    """
    url_lower = url.lower()
    if "greenhouse.io" in url_lower:
        return "greenhouse"
    if "jobs.lever.co" in url_lower:
        return "lever"
    if "myworkdayjobs.com" in url_lower or "workday.com" in url_lower:
        return "workday"
    if "linkedin.com/jobs" in url_lower:
        return "linkedin"
    return None


# ---------------------------------------------------------------------------
# Applicant profile builder
# ---------------------------------------------------------------------------

def _build_applicant(job: Job, resume_data: dict) -> dict:
    """Build the applicant dict from resume data and job context."""
    personal = resume_data.get("personal", {})
    name = personal.get("name", "") or ""
    name_parts = name.split(" ", 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    return {
        "first_name": first_name,
        "last_name": last_name,
        "name": name,
        "email": personal.get("email", ""),
        "phone": personal.get("phone", ""),
        "linkedin": personal.get("linkedin", ""),
        "github": personal.get("github", ""),
        "website": personal.get("website", ""),
        "org": "",  # current company — leave blank, looks better
        "job_title": job.title,
        "company": job.company,
        "experience_summary": _build_experience_summary(resume_data),
        "skills": ", ".join(resume_data.get("skills", [])),
    }


def _find_resume_path(job_id: int) -> str | None:
    """Return tailored resume path for this job, or fall back to base resume."""
    # Check for tailored resume version
    tailored = Path(f"data/resume_versions/resume_{job_id}.pdf")
    if tailored.exists():
        return str(tailored)
    # docx versions also accepted by most ATS
    tailored_docx = Path(f"data/resume_versions/resume_{job_id}.docx")
    if tailored_docx.exists():
        return str(tailored_docx)
    # Fall back to base resume
    for base in ["data/base_resume.pdf", "data/base_resume.docx"]:
        if Path(base).exists():
            return base
    return None


def _find_cover_letter_path(job_id: int) -> str | None:
    """Return cover letter path for this job if it exists."""
    for ext in ["docx", "pdf", "txt"]:
        p = Path(f"data/cover_letters/cover_letter_{job_id}.{ext}")
        if p.exists():
            return str(p)
    return None


def _load_cover_letter_text(job_id: int) -> str:
    """Read cover letter text from docx (for ATS text areas)."""
    path = Path(f"data/cover_letters/cover_letter_{job_id}.docx")
    if not path.exists():
        return ""
    try:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs[1:])  # skip subject line (first para)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Log to DB
# ---------------------------------------------------------------------------

def _log_application(job: Job, resume_path: str | None, cover_letter_path: str | None) -> None:
    """Record the application in the Application table and update job status."""
    with get_session() as db:
        existing = db.query(Application).filter(Application.job_id == job.id).first()
        if not existing:
            app = Application(
                job_id=job.id,
                applied_date=datetime.utcnow(),
                resume_version_path=resume_path or "",
                cover_letter_path=cover_letter_path or "",
                status="submitted",
            )
            db.add(app)

        # Update job status
        job_record = db.query(Job).filter(Job.id == job.id).first()
        if job_record:
            job_record.status = "applied"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_apply(job_id: int, submit: bool = False) -> None:
    """CLI entry point: python main.py apply --job-id <id>

    Args:
        job_id: Job to apply for.
        submit: If False (default), fills the form but does NOT click submit.
                If True, actually submits. Always review the screenshot first.
    """
    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        console.print(f"[red]No job found with ID {job_id}.[/red]")
        return

    if not job.fit_score:
        console.print(
            f"[yellow]Job {job_id} has not been scored. "
            f"Score it first: python main.py score --job-id {job_id}[/yellow]"
        )
        return

    # Detect ATS
    ats = detect_ats(job.url)
    if not ats:
        console.print(
            f"[yellow]Unsupported ATS for {job.url}[/yellow]\n"
            f"[dim]Supported: Greenhouse (greenhouse.io), Lever (lever.co)[/dim]"
        )
        return

    if ats in ("workday", "linkedin"):
        console.print(
            f"[yellow]{ats.title()} is not supported for auto-apply.[/yellow]\n"
            f"[dim]Apply manually at: {job.url}[/dim]"
        )
        return

    # Check prerequisites
    resume_path = _find_resume_path(job_id)
    if not resume_path:
        console.print(
            "[red]No resume found. Add data/base_resume.pdf or run: "
            "python main.py tailor --job-id {job_id}[/red]"
        )
        return

    cover_letter_path = _find_cover_letter_path(job_id)
    cover_letter_text = _load_cover_letter_text(job_id)

    resume_data = parse_resume()
    applicant = _build_applicant(job, resume_data)

    mode = "[yellow]DRY RUN[/yellow] — form will be filled but NOT submitted" if not submit else "[red]LIVE SUBMIT[/red]"
    console.print(f"\n[bold]Auto-Apply:[/bold] {job.title} @ {job.company}")
    console.print(f"[bold]ATS:[/bold] {ats.title()}   [bold]Mode:[/bold] {mode}\n")

    if submit:
        console.print(
            "[yellow]Warning: This will submit a real application. "
            "Review the dry-run screenshot first.[/yellow]\n"
        )

    fill_result = {}
    with console.status(f"{'Filling' if not submit else 'Submitting'} {ats.title()} form..."):
        try:
            if ats == "greenhouse":
                from tools.ats.greenhouse import fill_greenhouse_sync
                fill_result = fill_greenhouse_sync(
                    url=job.url,
                    applicant=applicant,
                    resume_path=resume_path,
                    cover_letter_path=cover_letter_path,
                    dry_run=not submit,
                )
            elif ats == "lever":
                from tools.ats.lever import fill_lever_sync
                fill_result = fill_lever_sync(
                    url=job.url,
                    applicant=applicant,
                    resume_path=resume_path,
                    cover_letter_text=cover_letter_text,
                    dry_run=not submit,
                )
        except Exception as e:
            console.print(f"[red]Autofill failed: {e}[/red]")
            return

    # Display results
    success = fill_result.get("success", False)
    fields = fill_result.get("filled_fields", [])
    custom = fill_result.get("custom_answered", 0)
    screenshot = fill_result.get("screenshot", "")
    error = fill_result.get("error", "")

    status_icon = "[green]✓[/green]" if success else "[red]✗[/red]"
    lines = [
        f"{status_icon} {'Filled' if not submit else 'Submitted'}: {job.title} @ {job.company}",
        f"Fields filled: {', '.join(fields) or 'none'}",
        f"Custom questions answered: {custom}",
    ]
    if screenshot:
        lines.append(f"Screenshot: {screenshot}")
    if error:
        lines.append(f"[red]Error: {error}[/red]")

    console.print(Panel(
        "\n".join(lines),
        title=f"[bold]{ats.title()} Auto-Fill[/bold]",
        border_style="green" if success else "red",
    ))

    if success and submit:
        _log_application(job, resume_path, cover_letter_path)
        console.print(f"[green]Application logged. Job status updated to 'applied'.[/green]")
    elif success and not submit:
        console.print(
            f"\n[dim]Review the screenshot above, then submit for real with:[/dim]"
        )
        console.print(f"  [bold]python main.py apply --job-id {job_id} --submit[/bold]")
