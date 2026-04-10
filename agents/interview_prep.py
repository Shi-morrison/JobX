from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from db.session import get_session
from db.models import Job, InterviewPrep
from tools.llm import ClaudeClient, load_prompt, parse_resume
from tools.leetcode import fetch_company_problems
from tools.glassdoor import fetch_glassdoor_interviews
from tools.levelsfyi import fetch_levelsfyi_compensation
from agents.scorer import _build_experience_summary

console = Console()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_or_create_prep(db, job_id: int) -> InterviewPrep:
    """Fetch existing InterviewPrep for a job or create a new blank one."""
    prep = db.query(InterviewPrep).filter(InterviewPrep.job_id == job_id).first()
    if not prep:
        prep = InterviewPrep(job_id=job_id, mock_sessions=[])
        db.add(prep)
        db.flush()
    return prep


def _load_job(job_id: int) -> Job | None:
    """Load and validate a job for interview prep."""
    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
    return job


# ---------------------------------------------------------------------------
# Task 3.5.1a — LeetCode Problem Fetcher
# ---------------------------------------------------------------------------

def fetch_leetcode_problems(company_name: str) -> dict:
    """Fetch real LeetCode problems for a company from the GitHub dataset.

    Returns the raw result dict from tools.leetcode.fetch_company_problems.
    """
    return fetch_company_problems(company_name, limit=20)


def _format_leetcode_context(lc_result: dict) -> str:
    """Format LeetCode problems into a readable string for the prompt."""
    if not lc_result.get("found") or not lc_result.get("problems"):
        return "No LeetCode company data found — generate questions based on the JD technologies."

    window_label = {
        "three-months": "last 3 months",
        "six-months": "last 6 months",
        "all": "all time",
    }.get(lc_result.get("window", ""), "recent")

    lines = [f"({window_label} data — sorted by frequency):"]
    for p in lc_result["problems"]:
        lines.append(
            f"  - {p['title']} ({p['difficulty']}) | "
            f"Frequency: {p['frequency']}% | "
            f"Acceptance: {p['acceptance']}% | "
            f"{p['url']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Task 3.5.1b — Glassdoor Interview Review Fetcher
# ---------------------------------------------------------------------------

def fetch_glassdoor_questions(company_name: str) -> dict:
    """Fetch reported interview questions from Glassdoor for a company."""
    return fetch_glassdoor_interviews(company_name, limit=20)


def _format_glassdoor_context(gd_result: dict) -> str:
    """Format Glassdoor questions into a readable string for the prompt."""
    if not gd_result.get("found") or not gd_result.get("questions"):
        return "No Glassdoor interview data found — generate questions based on JD and LeetCode data."

    lines = [f"(reported by past candidates — {len(gd_result['questions'])} questions):"]
    for q in gd_result["questions"]:
        difficulty = f" [{q['difficulty']}]" if q.get("difficulty") else ""
        outcome = f" — {q['outcome']}" if q.get("outcome") else ""
        lines.append(f"  - {q['question']}{difficulty}{outcome}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Task 3.5.1c — levels.fyi Compensation Fetcher
# ---------------------------------------------------------------------------

def fetch_compensation_data(company_name: str) -> dict:
    """Fetch salary/compensation data from levels.fyi for a company.

    Note: levels.fyi removed their interview section. This fetches comp data
    instead — useful context for offer evaluation and comp discussion rounds.
    """
    return fetch_levelsfyi_compensation(company_name)


def _format_compensation_context(comp_result: dict) -> str:
    """Format levels.fyi comp data into a readable string for prompts."""
    if not comp_result.get("found"):
        return "No levels.fyi compensation data found."

    lines = ["(from levels.fyi — verified compensation data):"]
    if comp_result.get("median_total_comp"):
        lines.append(f"  Median total comp (all roles): {comp_result['median_total_comp']}")
    if comp_result.get("software_engineer_median"):
        lines.append(f"  Software Engineer median: {comp_result['software_engineer_median']}")
    if comp_result.get("job_families"):
        lines.append("  Top roles by compensation:")
        for row in comp_result["job_families"][:6]:
            lines.append(f"    - {row['role']}: {row['median']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Task 3.5.2 — Tech Stack Question Generator
# ---------------------------------------------------------------------------

def generate_technical_questions(
    job: Job,
    resume_data: dict,
    lc_result: dict | None = None,
    gd_result: dict | None = None,
) -> dict:
    """Generate technical interview questions per technology mentioned in the JD.

    Incorporates real LeetCode problems and Glassdoor reported questions when
    available to ground the output in what this company actually asks.

    Args:
        job: The job being prepared for.
        resume_data: Parsed resume dict.
        lc_result: Optional result from fetch_leetcode_problems().
        gd_result: Optional result from fetch_glassdoor_questions().

    Returns:
        Dict with technical_questions: {technology: [question, ...]}
    """
    leetcode_context = _format_leetcode_context(lc_result) if lc_result else (
        "No LeetCode data provided — generate questions based on JD technologies."
    )
    glassdoor_context = _format_glassdoor_context(gd_result) if gd_result else (
        "No Glassdoor data provided — generate questions based on JD and LeetCode data."
    )

    prompt = load_prompt(
        "interview_technical",
        job_title=job.title,
        company=job.company,
        job_description=(job.description or "")[:3000],
        skills=", ".join(resume_data.get("skills", [])),
        leetcode_context=leetcode_context,
        glassdoor_context=glassdoor_context,
    )
    client = ClaudeClient()
    return client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )


# ---------------------------------------------------------------------------
# Task 3.5.3 — Behavioral Question Generator
# ---------------------------------------------------------------------------

def generate_behavioral_questions(job: Job, resume_data: dict) -> dict:
    """Generate STAR-format behavioral questions tailored to the JD's soft skill signals.

    Returns:
        Dict with behavioral_questions: [{question, trait, star_framework}]
    """
    prompt = load_prompt(
        "interview_behavioral",
        job_title=job.title,
        company=job.company,
        job_description=(job.description or "")[:3000],
        experience_summary=_build_experience_summary(resume_data),
    )
    client = ClaudeClient()
    return client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )


# ---------------------------------------------------------------------------
# Task 3.5.4 — Company-Specific Prep
# ---------------------------------------------------------------------------

def generate_company_questions(job: Job, resume_data: dict) -> dict:
    """Generate "why us" talking points and smart questions to ask the interviewer.

    Returns:
        Dict with company_questions and why_us_talking_points.
    """
    prompt = load_prompt(
        "interview_company",
        job_title=job.title,
        company=job.company,
        job_description=(job.description or "")[:3000],
        experience_summary=_build_experience_summary(resume_data),
    )
    client = ClaudeClient()
    return client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )


# ---------------------------------------------------------------------------
# Task 3.5.6 — Study Plan Generator
# ---------------------------------------------------------------------------

def generate_study_plan(job: Job, resume_data: dict, gap_analysis: dict) -> dict:
    """Generate a prioritized study plan from hard and soft gaps.

    Returns:
        Dict with study_plan: [{topic, priority, resources, estimated_hours, why}]
    """
    hard_gaps = gap_analysis.get("hard_gaps", [])
    soft_gaps = gap_analysis.get("soft_gaps", [])

    if not hard_gaps and not soft_gaps:
        return {"study_plan": []}

    prompt = load_prompt(
        "study_plan",
        job_title=job.title,
        company=job.company,
        hard_gaps=", ".join(hard_gaps) or "None",
        soft_gaps=", ".join(soft_gaps) or "None",
        skills=", ".join(resume_data.get("skills", [])),
    )
    client = ClaudeClient()
    return client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )


# ---------------------------------------------------------------------------
# run_prep — orchestrates 3.5.2, 3.5.3, 3.5.4, 3.5.6
# ---------------------------------------------------------------------------

def run_prep(job_id: int, force: bool = False) -> None:
    """Generate full interview prep for a job: technical questions, behavioral,
    company-specific, and study plan. Saves all results to the InterviewPrep table.

    Args:
        job_id: Job to prepare for. Must be scored first.
        force: Re-generate even if prep already exists.
    """
    job = _load_job(job_id)
    if not job:
        console.print(f"[red]No job found with ID {job_id}.[/red]")
        return

    if not job.fit_score:
        console.print(
            f"[yellow]Job {job_id} has not been scored yet. "
            f"Run: python main.py score --job-id {job_id}[/yellow]"
        )
        return

    # Check if prep already exists
    with get_session() as db:
        existing = db.query(InterviewPrep).filter(InterviewPrep.job_id == job_id).first()

    if existing and not force:
        console.print(
            f"[yellow]Interview prep already exists for job {job_id}. "
            f"Use [bold]--force[/bold] to regenerate.[/yellow]"
        )
        _print_prep_summary(existing, job)
        return

    resume_data = parse_resume()
    gap_analysis = job.gap_analysis or {}
    has_description = bool(job.description and job.description.strip() not in ("", "nan"))

    if not has_description:
        console.print(
            f"[yellow]Job {job_id} has no description. "
            f"Technical questions and study plan may be limited.[/yellow]"
        )

    console.print(f"\n[bold]Interview Prep:[/bold] {job.title} @ {job.company}\n")

    # Step 1: Fetch real LeetCode problems for this company
    lc_result = None
    with console.status(f"[1/6] Fetching LeetCode problems for {job.company}..."):
        try:
            lc_result = fetch_leetcode_problems(job.company)
            if lc_result.get("found"):
                count = len(lc_result["problems"])
                window = lc_result["window"]
                console.print(
                    f"  [green]✓[/green] Found {count} LeetCode problems "
                    f"({window.replace('-', ' ')} data)"
                )
            else:
                console.print(
                    f"  [dim]✗ {job.company} not in LeetCode dataset — "
                    f"using Claude-generated questions only[/dim]"
                )
        except Exception as e:
            console.print(f"[yellow]Warning: LeetCode fetch failed: {e}[/yellow]")

    # Step 2: Scrape Glassdoor interview reviews
    gd_result = None
    with console.status(f"[2/6] Scraping Glassdoor interview reviews for {job.company}..."):
        try:
            gd_result = fetch_glassdoor_questions(job.company)
            if gd_result.get("found"):
                count = len(gd_result["questions"])
                console.print(
                    f"  [green]✓[/green] Found {count} reported interview questions on Glassdoor"
                )
            else:
                console.print(
                    f"  [dim]✗ No Glassdoor data found for {job.company}[/dim]"
                )
        except Exception as e:
            console.print(f"[yellow]Warning: Glassdoor scrape failed: {e}[/yellow]")

    # Step 3: Fetch levels.fyi compensation data
    comp_result = None
    with console.status(f"[3/7] Fetching levels.fyi compensation data for {job.company}..."):
        try:
            comp_result = fetch_compensation_data(job.company)
            if comp_result.get("found"):
                median = comp_result.get("software_engineer_median") or comp_result.get("median_total_comp")
                console.print(
                    f"  [green]✓[/green] Found comp data "
                    f"(SWE median: {median})"
                )
            else:
                console.print(
                    f"  [dim]✗ No levels.fyi data found for {job.company}[/dim]"
                )
        except Exception as e:
            console.print(f"[yellow]Warning: levels.fyi fetch failed: {e}[/yellow]")

    # Step 4: Technical questions (grounded in LeetCode + Glassdoor data)
    with console.status("[4/7] Generating technical questions..."):
        try:
            technical = generate_technical_questions(job, resume_data, lc_result, gd_result)
        except Exception as e:
            console.print(f"[yellow]Warning: technical questions failed: {e}[/yellow]")
            technical = {"technical_questions": {}}

    # Step 5: Behavioral questions
    with console.status("[5/7] Generating behavioral questions..."):
        try:
            behavioral = generate_behavioral_questions(job, resume_data)
        except Exception as e:
            console.print(f"[yellow]Warning: behavioral questions failed: {e}[/yellow]")
            behavioral = {"behavioral_questions": []}

    # Step 6: Company-specific questions
    with console.status("[6/7] Generating company-specific prep..."):
        try:
            company = generate_company_questions(job, resume_data)
        except Exception as e:
            console.print(f"[yellow]Warning: company questions failed: {e}[/yellow]")
            company = {"company_questions": [], "why_us_talking_points": []}

    # Step 7: Study plan
    with console.status("[7/7] Generating study plan..."):
        try:
            study = generate_study_plan(job, resume_data, gap_analysis)
        except Exception as e:
            console.print(f"[yellow]Warning: study plan failed: {e}[/yellow]")
            study = {"study_plan": []}

    # Persist to DB
    with get_session() as db:
        prep = _get_or_create_prep(db, job_id)
        # Merge real data into technical_questions
        tech_questions = technical.get("technical_questions", {})
        if lc_result and lc_result.get("found") and lc_result.get("problems"):
            tech_questions["LeetCode"] = [
                f"{p['title']} ({p['difficulty']}) — {p['url']}"
                for p in lc_result["problems"]
            ]
        if gd_result and gd_result.get("found") and gd_result.get("questions"):
            tech_questions["Glassdoor"] = [
                q["question"] for q in gd_result["questions"]
            ]

        # Store comp data under company_questions for offer/negotiation context
        company_q = {
            "questions": company.get("company_questions", []),
            "why_us": company.get("why_us_talking_points", []),
        }
        if comp_result and comp_result.get("found"):
            company_q["compensation"] = {
                "median_total_comp": comp_result.get("median_total_comp", ""),
                "software_engineer_median": comp_result.get("software_engineer_median", ""),
                "job_families": comp_result.get("job_families", []),
                "source": "levels.fyi",
            }
        prep.technical_questions = tech_questions
        prep.behavioral_questions = behavioral.get("behavioral_questions", [])
        prep.company_questions = company_q
        prep.study_plan = study.get("study_plan", [])
        if not prep.mock_sessions:
            prep.mock_sessions = []

    console.print("[green]Interview prep saved.[/green]\n")

    # Re-load to display (fresh from DB)
    with get_session() as db:
        prep = db.query(InterviewPrep).filter(InterviewPrep.job_id == job_id).first()

    _print_prep_summary(prep, job)


def _print_prep_summary(prep: InterviewPrep, job: Job) -> None:
    """Display a summary of the saved interview prep."""
    tech_q = prep.technical_questions or {}
    behavioral_q = prep.behavioral_questions or []
    company_data = prep.company_questions or {}
    study = prep.study_plan or []

    total_tech = sum(len(qs) for qs in tech_q.values())
    console.print(f"[bold]Technical:[/bold] {total_tech} questions across {len(tech_q)} technologies")
    for tech, questions in tech_q.items():
        console.print(f"  [cyan]{tech}[/cyan] ({len(questions)} questions)")
        for q in questions[:2]:
            console.print(f"    • {q}")
        if len(questions) > 2:
            console.print(f"    [dim]... and {len(questions) - 2} more[/dim]")
    console.print()

    console.print(f"[bold]Behavioral:[/bold] {len(behavioral_q)} questions")
    for bq in behavioral_q[:3]:
        console.print(f"  • {bq['question']}")
        console.print(f"    [dim]Trait: {bq.get('trait', '—')}[/dim]")
    if len(behavioral_q) > 3:
        console.print(f"  [dim]... and {len(behavioral_q) - 3} more[/dim]")
    console.print()

    why_us = company_data.get("why_us", [])
    company_qs = company_data.get("questions", [])
    console.print(f"[bold]Company Prep:[/bold] {len(why_us)} 'why us' points, {len(company_qs)} questions to ask")
    for pt in why_us[:2]:
        console.print(f"  • {pt}")
    console.print()

    if study:
        console.print(f"[bold]Study Plan:[/bold] {len(study)} topics")
        table = Table(show_lines=True)
        table.add_column("Priority", width=8, justify="center")
        table.add_column("Topic", style="bold")
        table.add_column("Hours", width=6, justify="center")
        table.add_column("Why")
        for item in study:
            priority = item.get("priority", "—")
            color = "red" if priority == "high" else "yellow" if priority == "medium" else "dim"
            table.add_row(
                f"[{color}]{priority}[/{color}]",
                item.get("topic", "—"),
                str(item.get("estimated_hours", "—")),
                item.get("why", "—"),
            )
        console.print(table)
    else:
        console.print("[dim]No study plan items — no hard gaps identified.[/dim]")

    console.print(
        f"\n[dim]Run a mock interview: [bold]python main.py prep mock --job-id {job.id}[/bold][/dim]"
    )


# ---------------------------------------------------------------------------
# Task 3.5.5 — Mock Interview CLI Mode
# ---------------------------------------------------------------------------

def run_mock(job_id: int) -> None:
    """Run an interactive mock interview session for a job.

    Rotates through technical, behavioral, and company questions.
    Claude scores each answer and gives specific critique.
    Session saved to InterviewPrep.mock_sessions.
    """
    job = _load_job(job_id)
    if not job:
        console.print(f"[red]No job found with ID {job_id}.[/red]")
        return

    with get_session() as db:
        prep = db.query(InterviewPrep).filter(InterviewPrep.job_id == job_id).first()

    if not prep or (not prep.technical_questions and not prep.behavioral_questions):
        console.print(
            f"[yellow]No interview prep found for job {job_id}. "
            f"Run first: [bold]python main.py prep run --job-id {job_id}[/bold][/yellow]"
        )
        return

    # Build a flat question pool rotating: technical → behavioral → company
    questions = _build_question_pool(prep)
    if not questions:
        console.print("[yellow]No questions available for mock interview.[/yellow]")
        return

    console.print(Panel(
        f"[bold]Mock Interview — {job.title} @ {job.company}[/bold]\n"
        f"[dim]{len(questions)} questions queued. Type your answer and press Enter.\n"
        f"Type [bold]skip[/bold] to skip a question, [bold]quit[/bold] to end the session.[/dim]",
        expand=False,
    ))
    console.print()

    client = ClaudeClient()
    qa_pairs = []

    for i, q_item in enumerate(questions, 1):
        q_type = q_item["type"]
        question = q_item["question"]
        type_color = "cyan" if q_type == "technical" else "yellow" if q_type == "behavioral" else "green"

        console.print(f"[{type_color}][{q_type.upper()}][/{type_color}] Question {i} of {len(questions)}")
        console.print(f"[bold]{question}[/bold]")
        console.print()

        try:
            answer = input("Your answer: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if answer.lower() == "quit":
            break
        if answer.lower() == "skip":
            console.print("[dim]Skipped.[/dim]\n")
            continue
        if not answer:
            console.print("[dim]No answer given — skipping.[/dim]\n")
            continue

        # Ask Claude to score the answer
        with console.status("Evaluating your answer..."):
            feedback = _score_answer(client, question, answer, q_type, job)

        score = feedback.get("score", 0)
        score_color = "green" if score >= 8 else "yellow" if score >= 5 else "red"

        console.print(f"\n[{score_color}]Score: {score}/10[/{score_color}]")
        console.print(f"[bold]Feedback:[/bold] {feedback.get('critique', '—')}")
        if feedback.get("suggested_answer"):
            console.print(f"[bold]Stronger answer:[/bold]")
            console.print(f"  [dim]{feedback['suggested_answer']}[/dim]")
        console.print()

        qa_pairs.append({
            "type": q_type,
            "question": question,
            "answer": answer,
            "score": score,
            "critique": feedback.get("critique", ""),
            "suggested_answer": feedback.get("suggested_answer", ""),
        })

    if not qa_pairs:
        console.print("[dim]No answers recorded — session not saved.[/dim]")
        return

    # Save session to DB
    session_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "qa_pairs": qa_pairs,
        "avg_score": round(sum(p["score"] for p in qa_pairs) / len(qa_pairs), 1),
    }

    with get_session() as db:
        prep = db.query(InterviewPrep).filter(InterviewPrep.job_id == job_id).first()
        if prep:
            sessions = list(prep.mock_sessions or [])
            sessions.append(session_record)
            prep.mock_sessions = sessions

    avg = session_record["avg_score"]
    avg_color = "green" if avg >= 8 else "yellow" if avg >= 5 else "red"
    console.print(
        f"[bold]Session complete.[/bold] {len(qa_pairs)} questions answered. "
        f"Average score: [{avg_color}]{avg}/10[/{avg_color}]"
    )


def _build_question_pool(prep: InterviewPrep) -> list[dict]:
    """Build a flat list of questions rotating technical → behavioral → company."""
    technical = prep.technical_questions or {}
    behavioral = prep.behavioral_questions or []
    company_data = prep.company_questions or {}
    company_qs = company_data.get("questions", [])

    # Flatten technical questions across all technologies
    tech_flat = [
        {"type": "technical", "question": q}
        for qs in technical.values()
        for q in qs
    ]
    behavioral_flat = [
        {"type": "behavioral", "question": bq["question"]}
        for bq in behavioral
    ]
    company_flat = [
        {"type": "company", "question": cq["question"]}
        for cq in company_qs
    ]

    # Interleave: 2 technical, 1 behavioral, 1 company, repeat
    pool = []
    t, b, c = iter(tech_flat), iter(behavioral_flat), iter(company_flat)
    while True:
        added = False
        for _ in range(2):
            q = next(t, None)
            if q:
                pool.append(q)
                added = True
        q = next(b, None)
        if q:
            pool.append(q)
            added = True
        q = next(c, None)
        if q:
            pool.append(q)
            added = True
        if not added:
            break

    return pool


def _score_answer(client: ClaudeClient, question: str, answer: str, q_type: str, job: Job) -> dict:
    """Ask Claude to score and critique the candidate's interview answer."""
    prompt = (
        f"You are a senior interviewer at {job.company} evaluating a candidate for the role: {job.title}.\n\n"
        f"Question type: {q_type}\n"
        f"Question: {question}\n\n"
        f"Candidate's answer: {answer}\n\n"
        f"Score this answer 1–10 and give specific, actionable feedback. "
        f"If it's a behavioral question, evaluate STAR structure. "
        f"If it's technical, evaluate correctness and depth. "
        f"Then provide a concise example of a stronger answer.\n\n"
        f"Return only valid JSON:\n"
        f'{{"score": 0, "critique": "...", "suggested_answer": "..."}}'
    )
    return client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
