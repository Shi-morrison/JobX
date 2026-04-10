from rich.console import Console
from rich.table import Table

from db.session import get_session
from db.models import Job
from tools.llm import ClaudeClient, load_prompt, parse_resume

console = Console()


def _build_experience_summary(resume_data: dict) -> str:
    """Flatten experience into a compact string for the prompt."""
    lines = []
    for exp in resume_data.get("experience", []):
        lines.append(f"{exp['title']} at {exp['company']} ({exp.get('start_date','')} – {exp.get('end_date','')})")
        for bullet in exp.get("bullets", [])[:3]:  # top 3 bullets per role
            lines.append(f"  - {bullet}")
    return "\n".join(lines) if lines else "No experience listed."


# ---------------------------------------------------------------------------
# Task 2.2 — Fit Scorer
# ---------------------------------------------------------------------------

def score_fit(job: Job, resume_data: dict) -> dict:
    """Score how well the candidate fits a job using Claude.

    Returns:
        Dict with fit_score (1-10), matching_skills, missing_skills, reasoning.
    """
    skills = ", ".join(resume_data.get("skills", []))
    experience_summary = _build_experience_summary(resume_data)
    description = (job.description or "")[:4000]

    prompt = load_prompt(
        "score_fit",
        job_title=job.title,
        company=job.company,
        job_description=description,
        skills=skills,
        experience_summary=experience_summary,
    )

    client = ClaudeClient()
    result = client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )

    score = result.get("fit_score", 0)
    result["fit_score"] = max(1, min(10, int(score)))
    return result


# ---------------------------------------------------------------------------
# Task 2.3 — ATS Keyword Checker
# ---------------------------------------------------------------------------

def check_ats(job: Job, resume_data: dict) -> dict:
    """Extract JD keywords and score how many the candidate's resume covers.

    Returns:
        Dict with ats_score (0-100), matched_keywords, missing_keywords.
    """
    skills = ", ".join(resume_data.get("skills", []))
    description = (job.description or "")[:4000]

    prompt = load_prompt(
        "ats_check",
        job_title=job.title,
        job_description=description,
        skills=skills,
    )

    client = ClaudeClient()
    result = client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )

    # Clamp ats_score to 0-100
    score = float(result.get("ats_score", 0))
    result["ats_score"] = round(max(0.0, min(100.0, score)), 1)
    return result


# ---------------------------------------------------------------------------
# Task 2.4 — Gap Analyzer
# ---------------------------------------------------------------------------

def analyze_gaps(fit_result: dict, ats_result: dict, resume_data: dict) -> dict:
    """Combine fit + ATS results to classify gaps and suggest reframes.

    Returns:
        Dict with hard_gaps, soft_gaps, reframe_suggestions.
    """
    missing_skills = fit_result.get("missing_skills", [])
    missing_keywords = ats_result.get("missing_keywords", [])

    # If nothing is missing, return empty analysis without calling Claude
    if not missing_skills and not missing_keywords:
        return {"hard_gaps": [], "soft_gaps": [], "reframe_suggestions": []}

    skills = ", ".join(resume_data.get("skills", []))
    experience_summary = _build_experience_summary(resume_data)

    prompt = load_prompt(
        "gap_analysis",
        missing_skills=", ".join(missing_skills),
        missing_keywords=", ".join(missing_keywords),
        experience_summary=experience_summary,
        skills=skills,
    )

    client = ClaudeClient()
    result = client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return result


# ---------------------------------------------------------------------------
# run_scorer — orchestrates all three steps
# ---------------------------------------------------------------------------

def run_scorer(
    job_id: int | None = None,
    limit: int | None = None,
    min_score: int | None = None,
    show_reasoning: bool = False,
    force: bool = False,
    recent: bool = False,
) -> None:
    """Run fit scoring, ATS check, and gap analysis on jobs in the DB.

    Args:
        job_id: Score only this specific job (by DB id).
        limit: Max number of jobs to score in this run.
        min_score: Only display jobs at or above this score after scoring.
        show_reasoning: Print Claude's reasoning under each job score.
        force: Re-score jobs that already have a fit_score.
        recent: Sort by most recently posted first (use with --limit for newest N jobs).
    """
    resume_data = parse_resume()

    with get_session() as db:
        query = db.query(Job).filter(
            Job.description.isnot(None),
            Job.description != "",
            Job.description != "nan",
        )

        if job_id is not None:
            # Single job mode — ignore force, always score it
            query = query.filter(Job.id == job_id)
        elif not force:
            # Default: only unscored jobs
            query = query.filter(Job.fit_score.is_(None))

        if recent:
            query = query.order_by(Job.posted_date.desc().nulls_last())

        if limit is not None:
            query = query.limit(limit)

        candidates = query.all()

    if not candidates:
        if job_id is not None:
            console.print(f"[red]No scoreable job found with ID {job_id}. Check the ID with: python main.py jobs[/red]")
        else:
            console.print("[yellow]No unscored jobs found. Run [bold]python main.py search[/bold] first, or use [bold]--force[/bold] to re-score existing jobs.[/yellow]")
        return

    scope = f"job ID {job_id}" if job_id else f"{len(candidates)} job{'s' if len(candidates) != 1 else ''}"
    console.print(f"[dim]Running fit score + ATS check + gap analysis on {scope}...[/dim]")

    scored = []
    for job in candidates:
        with console.status(f"[1/3] Fit score: {job.title} @ {job.company}..."):
            try:
                fit = score_fit(job, resume_data)
            except Exception as e:
                console.print(f"[yellow]Warning: fit score failed for job {job.id}: {e}[/yellow]")
                continue

        with console.status(f"[2/3] ATS check: {job.title} @ {job.company}..."):
            try:
                ats = check_ats(job, resume_data)
            except Exception as e:
                console.print(f"[yellow]Warning: ATS check failed for job {job.id}: {e}[/yellow]")
                ats = {"ats_score": None, "matched_keywords": [], "missing_keywords": []}

        with console.status(f"[3/3] Gap analysis: {job.title} @ {job.company}..."):
            try:
                gaps = analyze_gaps(fit, ats, resume_data)
            except Exception as e:
                console.print(f"[yellow]Warning: gap analysis failed for job {job.id}: {e}[/yellow]")
                gaps = {"hard_gaps": [], "soft_gaps": [], "reframe_suggestions": []}

        # Persist all results to DB — store fit reasoning inside gap_analysis
        gap_analysis_data = {**gaps, "fit_reasoning": fit.get("reasoning", "")}
        with get_session() as db:
            db_job = db.query(Job).filter(Job.id == job.id).first()
            db_job.fit_score = fit["fit_score"]
            db_job.ats_score = ats.get("ats_score")
            db_job.gap_analysis = gap_analysis_data
            db_job.status = "scored"

        scored.append((job, fit, ats, gaps))

    if not scored:
        console.print("[yellow]No jobs could be scored.[/yellow]")
        return

    scored.sort(key=lambda x: x[1]["fit_score"], reverse=True)
    display = [(j, f, a, g) for j, f, a, g in scored if f["fit_score"] >= (min_score or 0)]
    _print_scored_table(display, total_scored=len(scored), show_reasoning=show_reasoning)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _print_scored_table(scored: list, total_scored: int, show_reasoning: bool = False) -> None:
    if not scored:
        console.print("[yellow]No jobs met the minimum score threshold.[/yellow]")
        return

    table = Table(title=f"[green]Scored {total_scored} Jobs — Top {len(scored)} Shown[/green]", show_lines=True)
    table.add_column("Fit", style="bold", width=6, justify="center")
    table.add_column("ATS%", width=6, justify="center")
    table.add_column("Title", style="bold")
    table.add_column("Company")
    table.add_column("Matching Skills")
    table.add_column("Hard Gaps")

    for job, fit, ats, gaps in scored:
        fit_score = fit["fit_score"]
        ats_score = ats.get("ats_score")
        score_color = "green" if fit_score >= 7 else "yellow" if fit_score >= 5 else "red"
        ats_str = f"{ats_score:.0f}%" if ats_score is not None else "—"
        matching = ", ".join(fit.get("matching_skills", [])[:3]) or "—"
        hard_gaps = ", ".join(gaps.get("hard_gaps", [])[:2]) or "—"

        table.add_row(
            f"[{score_color}]{fit_score}/10[/{score_color}]",
            ats_str,
            job.title,
            job.company,
            matching,
            hard_gaps,
        )

    console.print(table)

    if show_reasoning:
        console.print()
        for job, fit, ats, gaps in scored:
            fit_score = fit["fit_score"]
            score_color = "green" if fit_score >= 7 else "yellow" if fit_score >= 5 else "red"
            console.print(f"[{score_color}][bold]{fit_score}/10[/bold][/{score_color}] {job.title} @ {job.company}")
            console.print(f"  [dim]Fit: {fit.get('reasoning', '—')}[/dim]")
            if gaps.get("soft_gaps"):
                console.print(f"  [dim]Soft gaps (reframeable): {', '.join(gaps['soft_gaps'])}[/dim]")
            if gaps.get("hard_gaps"):
                console.print(f"  [dim]Hard gaps: {', '.join(gaps['hard_gaps'])}[/dim]")
            console.print()
    else:
        console.print("[dim]Run [bold]python main.py score --show-reasoning[/bold] to see full reasoning per job.[/dim]")
