"""Company Research Agent (Phase 4.1).

Aggregates company intelligence from multiple sources:
  - levels.fyi  → funding stage, valuation, industry, employee count
  - Glassdoor   → overall rating
  - StackShare  → tech stack
  - SerpAPI     → recent news + layoff history (optional — requires SERPAPI_KEY)

Claude synthesizes the raw data into a 2–3 sentence summary and signals.
Results are stored in the CompanyResearch table and reused by cover letters
and interview prep automatically.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from db.session import get_session
from db.models import CompanyResearch
from tools.llm import ClaudeClient, load_prompt

console = Console()


# ---------------------------------------------------------------------------
# Raw data fetchers
# ---------------------------------------------------------------------------

def _fetch_meta(company_name: str) -> dict:
    from tools.levelsfyi import fetch_company_meta
    return fetch_company_meta(company_name)


def _fetch_rating(company_name: str) -> dict:
    from tools.glassdoor import fetch_glassdoor_rating
    return fetch_glassdoor_rating(company_name)


def _fetch_stack(company_name: str) -> dict:
    from tools.stackshare import fetch_tech_stack
    return fetch_tech_stack(company_name)


def _fetch_news(company_name: str) -> list[dict]:
    from tools.search import search_web
    results = search_web(f'"{company_name}" company news 2024 OR 2025', num_results=5)
    return results


def _fetch_layoffs(company_name: str) -> list[dict]:
    from tools.search import search_web
    results = search_web(f'"{company_name}" layoffs OR "laid off" OR "workforce reduction"', num_results=3)
    return results


# ---------------------------------------------------------------------------
# Context formatters for the Claude prompt
# ---------------------------------------------------------------------------

def _fmt_meta(meta: dict) -> str:
    if not meta.get("found"):
        return "Not found."
    parts = []
    if meta.get("industry"):
        parts.append(f"Industry: {meta['industry']}")
    if meta.get("funding_stage"):
        parts.append(f"Funding stage: {meta['funding_stage']}")
    if meta.get("estimated_valuation"):
        parts.append(f"Estimated valuation: {meta['estimated_valuation']}")
    if meta.get("employee_count"):
        parts.append(f"Employees: {meta['employee_count']}")
    if meta.get("description"):
        parts.append(f"Description: {meta['description']}")
    return "\n".join(parts) if parts else "Not found."


def _fmt_rating(rating: dict) -> str:
    if not rating.get("found") or rating.get("rating") is None:
        return "Not found."
    parts = [f"Overall rating: {rating['rating']} / 5"]
    if rating.get("review_count"):
        parts.append(f"Based on {rating['review_count']} reviews")
    return " — ".join(parts)


def _fmt_stack(stack: dict) -> str:
    if not stack.get("found") or not stack.get("tools"):
        return "Not found."
    return ", ".join(stack["tools"][:20])


def _fmt_news(news: list[dict]) -> str:
    if not news:
        return "No news found (SerpAPI key not configured or no results)."
    return "\n".join(f"- {n['title']}: {n['snippet']}" for n in news)


def _fmt_layoffs(layoffs: list[dict]) -> str:
    if not layoffs:
        return "No layoff news found."
    return "\n".join(f"- {n['title']}: {n['snippet']}" for n in layoffs)


# ---------------------------------------------------------------------------
# Core research function
# ---------------------------------------------------------------------------

def research_company(company_name: str, force: bool = False) -> dict:
    """Run the full company research pipeline and save to DB.

    Returns a dict with all gathered intel (also stored in CompanyResearch table).
    If research already exists and force=False, returns the cached DB record.
    """
    # Check cache
    with get_session() as db:
        existing = db.query(CompanyResearch).filter(
            CompanyResearch.company_name == company_name
        ).first()

    if existing and not force:
        return _record_to_dict(existing)

    console.print(f"\n[bold]Researching:[/bold] {company_name}\n")

    # Step 1: levels.fyi meta
    meta = {}
    with console.status("[1/5] Fetching company info from levels.fyi..."):
        try:
            meta = _fetch_meta(company_name)
            status = f"[green]✓[/green] {meta.get('industry', '')} — {meta.get('funding_stage', '')}" if meta.get("found") else "[dim]✗ Not found[/dim]"
            console.print(f"  {status}")
        except Exception as e:
            console.print(f"  [yellow]Warning: {e}[/yellow]")

    # Step 2: Glassdoor rating
    rating = {}
    with console.status("[2/5] Fetching Glassdoor rating..."):
        try:
            rating = _fetch_rating(company_name)
            status = f"[green]✓[/green] {rating['rating']} / 5" if rating.get("found") else "[dim]✗ Not found[/dim]"
            console.print(f"  {status}")
        except Exception as e:
            console.print(f"  [yellow]Warning: {e}[/yellow]")

    # Step 3: Tech stack
    stack = {}
    with console.status("[3/5] Fetching tech stack from StackShare..."):
        try:
            stack = _fetch_stack(company_name)
            status = f"[green]✓[/green] {len(stack.get('tools', []))} tools found" if stack.get("found") else "[dim]✗ Not found[/dim]"
            console.print(f"  {status}")
        except Exception as e:
            console.print(f"  [yellow]Warning: {e}[/yellow]")

    # Step 4: News (SerpAPI — optional)
    news = []
    with console.status("[4/5] Searching for recent news..."):
        try:
            news = _fetch_news(company_name)
            status = f"[green]✓[/green] {len(news)} articles found" if news else "[dim]✗ No results (configure SERPAPI_KEY for news)[/dim]"
            console.print(f"  {status}")
        except Exception as e:
            console.print(f"  [yellow]Warning: {e}[/yellow]")

    # Step 5: Layoff history (SerpAPI — optional)
    layoffs = []
    with console.status("[5/5] Checking for layoff history..."):
        try:
            layoffs = _fetch_layoffs(company_name)
            status = f"[yellow]⚠[/yellow] {len(layoffs)} layoff results found" if layoffs else "[dim]✗ No layoff news found[/dim]"
            console.print(f"  {status}")
        except Exception as e:
            console.print(f"  [yellow]Warning: {e}[/yellow]")

    # Claude synthesis
    with console.status("Synthesizing with Claude..."):
        try:
            prompt = load_prompt(
                "company_research",
                company=company_name,
                meta_context=_fmt_meta(meta),
                glassdoor_context=_fmt_rating(rating),
                techstack_context=_fmt_stack(stack),
                news_context=_fmt_news(news),
                layoff_context=_fmt_layoffs(layoffs),
            )
            client = ClaudeClient()
            synthesis = client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
        except Exception as e:
            console.print(f"  [yellow]Warning: synthesis failed: {e}[/yellow]")
            synthesis = {"summary": "", "signals": {}}

    # Persist to DB
    with get_session() as db:
        record = db.query(CompanyResearch).filter(
            CompanyResearch.company_name == company_name
        ).first()
        if not record:
            record = CompanyResearch(company_name=company_name)
            db.add(record)

        record.glassdoor_rating = rating.get("rating")
        record.funding_stage = meta.get("funding_stage") or ""
        record.employee_count = meta.get("employee_count") or ""
        record.industry = meta.get("industry") or ""
        record.tech_stack = stack.get("tools", [])
        record.recent_news = news
        record.layoff_history = layoffs
        record.summary = synthesis.get("summary", "")

    result = {
        "company_name": company_name,
        "summary": synthesis.get("summary", ""),
        "signals": synthesis.get("signals", {}),
        "glassdoor_rating": rating.get("rating"),
        "funding_stage": meta.get("funding_stage", ""),
        "employee_count": meta.get("employee_count", ""),
        "industry": meta.get("industry", ""),
        "tech_stack": stack.get("tools", []),
        "recent_news": news,
        "layoff_history": layoffs,
    }

    console.print()
    _print_summary(result)
    return result


def _record_to_dict(record: CompanyResearch) -> dict:
    return {
        "company_name": record.company_name,
        "summary": record.summary or "",
        "signals": {},
        "glassdoor_rating": record.glassdoor_rating,
        "funding_stage": record.funding_stage or "",
        "employee_count": record.employee_count or "",
        "industry": record.industry or "",
        "tech_stack": record.tech_stack or [],
        "recent_news": record.recent_news or [],
        "layoff_history": record.layoff_history or [],
    }


def get_cached_research(company_name: str) -> dict | None:
    """Return cached CompanyResearch for a company, or None if not researched yet."""
    with get_session() as db:
        record = db.query(CompanyResearch).filter(
            CompanyResearch.company_name == company_name
        ).first()
    return _record_to_dict(record) if record else None


def _print_summary(result: dict) -> None:
    signals = result.get("signals", {})
    stability = signals.get("stability_flag", "unknown")
    stability_color = {"stable": "green", "caution": "yellow", "layoff-risk": "red"}.get(stability, "dim")

    panel_lines = []
    if result.get("summary"):
        panel_lines.append(result["summary"])
        panel_lines.append("")
    if result.get("industry"):
        panel_lines.append(f"[bold]Industry:[/bold] {result['industry']}")
    if result.get("funding_stage"):
        panel_lines.append(f"[bold]Stage:[/bold] {result['funding_stage']}")
    if result.get("employee_count"):
        panel_lines.append(f"[bold]Employees:[/bold] {result['employee_count']}")
    if result.get("glassdoor_rating"):
        panel_lines.append(f"[bold]Glassdoor:[/bold] {result['glassdoor_rating']} / 5")
    if signals.get("stability_flag"):
        panel_lines.append(f"[bold]Stability:[/bold] [{stability_color}]{stability}[/{stability_color}]")
    if result.get("tech_stack"):
        panel_lines.append(f"[bold]Tech stack:[/bold] {', '.join(result['tech_stack'][:10])}")
    if result.get("recent_news"):
        panel_lines.append(f"\n[bold]Recent news ({len(result['recent_news'])} articles):[/bold]")
        for n in result["recent_news"][:3]:
            panel_lines.append(f"  • {n['title']}")
    if result.get("layoff_history"):
        panel_lines.append(f"\n[yellow bold]Layoff signals ({len(result['layoff_history'])} found):[/yellow bold]")
        for l in result["layoff_history"][:2]:
            panel_lines.append(f"  • {l['title']}")

    console.print(Panel(
        "\n".join(panel_lines),
        title=f"[bold]{result['company_name']}[/bold]",
        border_style="blue",
    ))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_research(company: str, force: bool = False) -> None:
    """CLI entry point for python main.py research --company "Stripe"."""
    research_company(company, force=force)
