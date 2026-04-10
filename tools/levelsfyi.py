"""levels.fyi salary data fetcher.

levels.fyi removed their interview section — interview questions are covered
by LeetCode (3.5.1a) and Glassdoor (3.5.1b). This module fetches compensation
data instead, which is useful context for:
  - Understanding the role level and expectations
  - Discussing comp during interviews
  - Offer evaluation

levels.fyi provides a public LLM-friendly markdown endpoint:
  https://www.levels.fyi/companies/{slug}/salaries.md
No auth or scraping required.
"""

import re
import requests
from rich.console import Console

console = Console()

_SALARY_URL = "https://www.levels.fyi/companies/{slug}/salaries.md"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/markdown, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _company_slug(name: str) -> str:
    """Normalize company name to levels.fyi URL slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def _parse_markdown(text: str) -> dict:
    """Extract key compensation metrics from the levels.fyi markdown response."""
    result = {
        "median_total_comp": "",
        "software_engineer_median": "",
        "job_families": [],
        "raw_summary": "",
    }

    # Median total comp (all roles)
    m = re.search(r"Median Total Compensation[^:]*:\s*\$?([\d,]+)", text)
    if m:
        result["median_total_comp"] = f"${m.group(1)}"

    # Job family table rows: | rank | Job Family | $amount |
    family_rows = re.findall(r"\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*\$([\d,]+)\s*\|", text)
    result["job_families"] = [
        {"role": row[0].strip(), "median": f"${row[1]}"}
        for row in family_rows[:10]
    ]

    # Software Engineer median for quick access
    for row in result["job_families"]:
        if "software engineer" in row["role"].lower() and "manager" not in row["role"].lower():
            result["software_engineer_median"] = row["median"]
            break

    # Compact summary: metadata + aggregate line
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    result["raw_summary"] = "\n".join(lines[:15])

    return result


def fetch_levelsfyi_compensation(company_name: str) -> dict:
    """Fetch salary / compensation data from levels.fyi for a company.

    Uses levels.fyi's public LLM-readable markdown endpoint — no auth required.

    Args:
        company_name: Company name as stored in the job record.

    Returns:
        {
            "found": bool,
            "company_slug": str,
            "url": str,
            "median_total_comp": str,            # e.g. "$296,944"
            "software_engineer_median": str,     # e.g. "$606,020"
            "job_families": [{"role": str, "median": str}],
            "raw_summary": str,                  # first ~15 lines of markdown
        }
    """
    slug = _company_slug(company_name)
    url = _SALARY_URL.format(slug=slug)

    base = {
        "found": False,
        "company_slug": slug,
        "url": url,
        "median_total_comp": "",
        "software_engineer_median": "",
        "job_families": [],
        "raw_summary": "",
    }

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            return base

        parsed = _parse_markdown(resp.text)
        found = bool(parsed["median_total_comp"] or parsed["levels"] or parsed["raw_summary"])

        return {**base, **parsed, "found": found}

    except Exception as e:
        console.print(f"[yellow]  levels.fyi fetch failed: {e}[/yellow]")
        return base
