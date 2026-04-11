"""Outreach Agent (Phase 5.3 + 5.4).

Manages the full outreach lifecycle for a job:
  - Generates personalized LinkedIn DM + email for each contact
  - Tracks send status in OutreachSequence table
  - Surfaces follow-ups due today
  - Optional Gmail send (requires google OAuth token.json)

Workflow:
  1. python main.py outreach --job-id 12          → find contacts + generate messages
  2. python main.py outreach --job-id 12 --send   → also send via Gmail (if configured)
  3. python main.py outreach --due                → show all follow-ups due today
"""

from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from db.session import get_session
from db.models import Job, Contact, OutreachSequence
from tools.llm import ClaudeClient, load_prompt, parse_resume
from agents.scorer import _build_experience_summary

console = Console()

FOLLOW_UP_DAYS = 5   # days after send before follow-up
GHOST_DAYS = 10      # days after follow-up before marking ghosted


# ---------------------------------------------------------------------------
# Message generation
# ---------------------------------------------------------------------------

def generate_messages(
    contact: Contact,
    job: Job,
    resume_data: dict,
    company_intel: str = "",
) -> dict:
    """Generate LinkedIn DM and email for a contact using Claude.

    Returns:
        {"dm": str, "subject": str, "email": str}
    """
    experience_summary = _build_experience_summary(resume_data)
    client = ClaudeClient()

    # DM
    dm_prompt = load_prompt(
        "outreach_dm",
        contact_name=contact.name or "there",
        contact_title=contact.title or "professional",
        company=job.company,
        job_title=job.title,
        experience_summary=experience_summary,
        company_intel=company_intel or "No company research available.",
    )
    dm_result = client.chat_json(
        messages=[{"role": "user", "content": dm_prompt}],
        max_tokens=256,
    )

    # Email
    email_prompt = load_prompt(
        "outreach_email",
        contact_name=contact.name or "there",
        contact_title=contact.title or "professional",
        company=job.company,
        job_title=job.title,
        experience_summary=experience_summary,
        company_intel=company_intel or "No company research available.",
    )
    email_result = client.chat_json(
        messages=[{"role": "user", "content": email_prompt}],
        max_tokens=512,
    )

    return {
        "dm": dm_result.get("dm", ""),
        "subject": email_result.get("subject", f"Software Engineer role at {job.company}"),
        "email": email_result.get("email", ""),
    }


# ---------------------------------------------------------------------------
# Sequence persistence
# ---------------------------------------------------------------------------

def _save_sequence(
    contact: Contact,
    message_type: str,
    content: str,
) -> OutreachSequence:
    """Create or return an OutreachSequence record for this contact + type."""
    with get_session() as db:
        existing = db.query(OutreachSequence).filter(
            OutreachSequence.contact_id == contact.id,
            OutreachSequence.message_type == message_type,
        ).first()
        if existing:
            # Update content if regenerated
            existing.content = content
            return existing

        seq = OutreachSequence(
            contact_id=contact.id,
            message_type=message_type,
            content=content,
            status="pending",
        )
        db.add(seq)
    return seq


def mark_sent(sequence_id: int, message_type: str = "linkedin") -> None:
    """Mark a sequence as sent and set follow_up_due."""
    with get_session() as db:
        seq = db.query(OutreachSequence).filter(
            OutreachSequence.id == sequence_id,
        ).first()
        if seq:
            seq.sent_at = datetime.utcnow()
            seq.follow_up_due = datetime.utcnow() + timedelta(days=FOLLOW_UP_DAYS)
            seq.status = "sent"


def mark_responded(sequence_id: int) -> None:
    """Mark a sequence as responded."""
    with get_session() as db:
        seq = db.query(OutreachSequence).filter(
            OutreachSequence.id == sequence_id,
        ).first()
        if seq:
            seq.response_received = True
            seq.status = "responded"


# ---------------------------------------------------------------------------
# Optional Gmail send
# ---------------------------------------------------------------------------

def _send_gmail(to_email: str, subject: str, body: str) -> bool:
    """Send an email via Gmail API. Returns True on success.

    Requires:
      - GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env
      - token.json in the project root (created by OAuth flow)

    Run `python -c "from tools.gmail_auth import run_auth_flow; run_auth_flow()"`
    to set up token.json.
    """
    token_path = Path("token.json")
    if not token_path.exists():
        return False

    try:
        import base64
        from email.mime.text import MIMEText
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(token_path))
        service = build("gmail", "v1", credentials=creds)

        message = MIMEText(body)
        message["to"] = to_email
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        return True

    except Exception as e:
        console.print(f"[yellow]Gmail send failed: {e}[/yellow]")
        return False


# ---------------------------------------------------------------------------
# Due follow-ups
# ---------------------------------------------------------------------------

def get_due_followups() -> list[dict]:
    """Return outreach sequences where follow_up_due <= now and not yet responded."""
    now = datetime.utcnow()
    results = []

    with get_session() as db:
        seqs = db.query(OutreachSequence).filter(
            OutreachSequence.follow_up_due <= now,
            OutreachSequence.response_received == False,  # noqa: E712
            OutreachSequence.status.in_(["sent", "followed_up"]),
        ).all()

        for seq in seqs:
            contact = db.query(Contact).filter(Contact.id == seq.contact_id).first()
            job = db.query(Job).filter(Job.id == contact.job_id).first() if contact else None
            days_since = (now - seq.sent_at).days if seq.sent_at else 0
            results.append({
                "seq_id": seq.id,
                "contact_name": contact.name if contact else "—",
                "contact_title": contact.title if contact else "—",
                "company": contact.company if contact else "—",
                "job_title": job.title if job else "—",
                "message_type": seq.message_type,
                "sent_at": seq.sent_at,
                "days_since": days_since,
                "status": seq.status,
                "ghosted": days_since >= GHOST_DAYS,
            })

    return results


def auto_ghost_stale() -> int:
    """Mark as ghosted any sequences where follow_up_due is 10+ days old. Returns count."""
    cutoff = datetime.utcnow() - timedelta(days=GHOST_DAYS)
    count = 0
    with get_session() as db:
        stale = db.query(OutreachSequence).filter(
            OutreachSequence.sent_at <= cutoff,
            OutreachSequence.response_received == False,  # noqa: E712
            OutreachSequence.status.in_(["sent", "followed_up"]),
        ).all()
        for seq in stale:
            seq.status = "ghosted"
            count += 1
    return count


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------

def run_outreach(
    job_id: int | None = None,
    send: bool = False,
    messages: bool = False,
) -> None:
    """Find contacts and generate outreach messages for a job.

    Args:
        job_id: Job to research contacts for.
        send:   If True and contact has email, attempt Gmail send.
        messages: If True, display generated message text.
    """
    if job_id is None:
        console.print("[red]Provide a job ID: python main.py outreach --job-id <id>[/red]")
        return

    with get_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        console.print(f"[red]No job found with ID {job_id}.[/red]")
        return

    # Load contacts (previously found via referrals or contact-finder)
    with get_session() as db:
        contacts = db.query(Contact).filter(Contact.job_id == job_id).all()

    if not contacts:
        console.print(
            f"[yellow]No contacts found for job {job_id}.[/yellow]\n"
            f"[dim]Find contacts first:[/dim]\n"
            f"  [bold]python main.py referrals --job-id {job_id}[/bold]   (LinkedIn CSV)\n"
            f"  [bold]python main.py find-contacts --job-id {job_id}[/bold]   (SerpAPI search)"
        )
        return

    # Company intel
    company_intel = ""
    try:
        from agents.company_research import get_cached_research
        research = get_cached_research(job.company)
        if research:
            parts = []
            if research.get("summary"):
                parts.append(research["summary"])
            if research.get("funding_stage"):
                parts.append(f"Stage: {research['funding_stage']}")
            company_intel = " | ".join(parts)
    except Exception:
        pass

    resume_data = parse_resume()

    console.print(f"\n[bold]Outreach:[/bold] {job.title} @ {job.company}\n")
    console.print(f"[dim]Generating messages for {len(contacts)} contact(s)...[/dim]\n")

    for contact in contacts:
        console.print(f"  [bold]{contact.name or 'Unknown'}[/bold] — {contact.title or '—'}")

        msgs = {}
        with console.status(f"  Writing messages for {contact.name or 'contact'}..."):
            try:
                msgs = generate_messages(contact, job, resume_data, company_intel)
            except Exception as e:
                console.print(f"  [yellow]  Warning: message generation failed: {e}[/yellow]")
                continue

        # Save sequences
        _save_sequence(contact, "linkedin", msgs.get("dm", ""))
        _save_sequence(contact, "email", msgs.get("email", ""))

        if messages or send:
            dm_text = msgs.get("dm", "")
            email_text = msgs.get("email", "")
            subject = msgs.get("subject", "")

            console.print(Panel(
                f"[bold]LinkedIn DM[/bold] ({len(dm_text)} chars):\n{dm_text}\n\n"
                f"[bold]Email — {subject}[/bold]\n{email_text}",
                title=f"{contact.name} @ {job.company}",
                expand=False,
            ))

        # Optional Gmail send
        if send and contact.email:
            email_text = msgs.get("email", "")
            subject = msgs.get("subject", "")
            with console.status(f"  Sending email to {contact.email}..."):
                ok = _send_gmail(contact.email, subject, email_text)
            if ok:
                console.print(f"  [green]✓[/green] Email sent to {contact.email}")
                # Mark the email sequence as sent
                with get_session() as db:
                    seq = db.query(OutreachSequence).filter(
                        OutreachSequence.contact_id == contact.id,
                        OutreachSequence.message_type == "email",
                    ).first()
                    if seq:
                        seq.sent_at = datetime.utcnow()
                        seq.follow_up_due = datetime.utcnow() + timedelta(days=FOLLOW_UP_DAYS)
                        seq.status = "sent"
            else:
                console.print(
                    f"  [dim]Gmail not configured — message saved for manual send.[/dim]"
                )
        elif send:
            console.print(f"  [dim]No email for {contact.name} — LinkedIn DM only.[/dim]")

    console.print()
    console.print("[dim]Messages saved. To send via Gmail, add token.json and use --send.[/dim]")
    console.print(
        "[dim]Check follow-ups: [bold]python main.py outreach --due[/bold][/dim]"
    )


def run_due_followups() -> None:
    """Display all outreach sequences with follow-ups due today."""
    # Auto-ghost stale sequences first
    ghosted_count = auto_ghost_stale()
    if ghosted_count:
        console.print(f"[dim]Marked {ghosted_count} stale outreach(es) as ghosted.[/dim]\n")

    due = get_due_followups()

    if not due:
        console.print("[green]No follow-ups due today.[/green]")
        return

    table = Table(
        title=f"[yellow]{len(due)} Follow-Up(s) Due[/yellow]",
        show_lines=True,
    )
    table.add_column("Contact", style="bold")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Job")
    table.add_column("Type", width=10)
    table.add_column("Days Since", justify="center")
    table.add_column("Status")

    for d in due:
        status_color = "red" if d["ghosted"] else "yellow"
        status_label = "ghost?" if d["ghosted"] else d["status"]
        table.add_row(
            d["contact_name"],
            d["contact_title"],
            d["company"],
            d["job_title"],
            d["message_type"],
            str(d["days_since"]),
            f"[{status_color}]{status_label}[/{status_color}]",
        )

    console.print(table)
    console.print()
    console.print(
        "[dim]To mark a contact as responded, update their OutreachSequence status in the DB.[/dim]"
    )
