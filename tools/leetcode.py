"""LeetCode company-wise problem fetcher.

Uses the snehasishroy/leetcode-companywise-interview-questions GitHub dataset
which contains company-tagged problems with frequency data sourced from LeetCode.
663 companies available. Problems sorted by frequency (most asked first).

Data windows available per company:
  - three-months  — most recent, highest signal
  - six-months    — broader recent history
  - all           — all-time

No auth required — pure HTTP fetch from GitHub raw content.
"""

import csv
import io
import re
import requests
from typing import Optional

_BASE_URL = (
    "https://raw.githubusercontent.com/"
    "snehasishroy/leetcode-companywise-interview-questions/master"
)

_COMPANY_LIST_URL = (
    "https://api.github.com/repos/"
    "snehasishroy/leetcode-companywise-interview-questions/contents"
)

# Cache the available company slugs so we only fetch the listing once per run
_available_companies: set[str] | None = None


def _company_slug(company_name: str) -> str:
    """Normalize a company name to a repo slug.

    Examples:
        "Robinhood"     -> "robinhood"
        "Goldman Sachs" -> "goldman-sachs"
        "J.P. Morgan"   -> "jp-morgan"
        "DoorDash"      -> "doordash"
    """
    slug = company_name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)   # strip punctuation
    slug = re.sub(r"\s+", "-", slug.strip())     # spaces -> hyphens
    slug = re.sub(r"-+", "-", slug)              # collapse double hyphens
    return slug


def _fetch_available_companies() -> set[str]:
    """Fetch the list of available company slugs from the GitHub repo."""
    global _available_companies
    if _available_companies is not None:
        return _available_companies

    try:
        resp = requests.get(_COMPANY_LIST_URL, timeout=10)
        resp.raise_for_status()
        entries = resp.json()
        _available_companies = {
            e["name"] for e in entries if e["type"] == "dir"
        }
    except Exception:
        _available_companies = set()

    return _available_companies


def _fetch_csv(company_slug: str, window: str) -> list[dict] | None:
    """Fetch and parse a company's problem CSV for a given time window.

    Returns list of problem dicts, or None if the file doesn't exist.
    """
    url = f"{_BASE_URL}/{company_slug}/{window}.csv"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        return list(reader)
    except Exception:
        return None


def fetch_company_problems(
    company_name: str,
    limit: int = 20,
) -> dict:
    """Fetch the most frequently asked LeetCode problems for a company.

    Tries time windows in order: three-months → six-months → all.
    Falls back gracefully if company not found.

    Args:
        company_name: Company name as stored in the job (e.g. "Robinhood").
        limit: Max number of problems to return.

    Returns:
        Dict with:
            found (bool): Whether company data was found.
            company_slug (str): Normalized slug used for lookup.
            window (str): Which time window data came from.
            problems (list): [{title, difficulty, url, frequency, acceptance}]
    """
    slug = _company_slug(company_name)
    available = _fetch_available_companies()

    # Check if company exists in dataset
    if available and slug not in available:
        # Try common variations before giving up
        variations = [
            slug.replace("-", ""),           # goldmansachs
            slug.split("-")[0],              # jp (from jp-morgan)
        ]
        matched = next((v for v in variations if v in available), None)
        if matched:
            slug = matched
        else:
            return {"found": False, "company_slug": slug, "window": None, "problems": []}

    # Try windows in order of recency
    for window in ("three-months", "six-months", "all"):
        rows = _fetch_csv(slug, window)
        if rows:
            problems = []
            for row in rows[:limit]:
                try:
                    freq = float(row.get("Frequency %", "0").replace("%", ""))
                    acc = float(row.get("Acceptance %", "0").replace("%", ""))
                except ValueError:
                    freq, acc = 0.0, 0.0

                problems.append({
                    "title": row.get("Title", "").strip(),
                    "difficulty": row.get("Difficulty", "").strip(),
                    "url": row.get("URL", "").strip(),
                    "frequency": round(freq, 1),
                    "acceptance": round(acc, 1),
                })

            return {
                "found": True,
                "company_slug": slug,
                "window": window,
                "problems": problems,
            }

    return {"found": False, "company_slug": slug, "window": None, "problems": []}
