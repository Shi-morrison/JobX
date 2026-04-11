"""StackShare tech stack scraper.

Fetches the public tech stack for a company from stackshare.io.
StackShare pages are server-rendered HTML — no JS/Playwright needed.
"""

import re
import requests
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()

_BASE_URL = "https://stackshare.io/{slug}"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _company_slug(name: str) -> str:
    """Normalize company name to StackShare URL slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def fetch_tech_stack(company_name: str) -> dict:
    """Fetch the tech stack for a company from StackShare.

    Args:
        company_name: Company name as stored in the job record.

    Returns:
        {
            "found": bool,
            "company_slug": str,
            "url": str,
            "tools": [str],   # list of technology/tool names
        }
    """
    slug = _company_slug(company_name)
    url = _BASE_URL.format(slug=slug)

    base = {"found": False, "company_slug": slug, "url": url, "tools": []}

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        if resp.status_code != 200:
            return base

        soup = BeautifulSoup(resp.text, "html.parser")

        tools: list[str] = []

        # StackShare renders tool names in <h4> or <a> tags inside stack sections
        # Try data attributes first (more stable), then class-based selectors
        for el in soup.select("[data-tool-name]"):
            name = el.get("data-tool-name", "").strip()
            if name:
                tools.append(name)

        # Fallback: look for tool cards by common class patterns
        if not tools:
            for el in soup.select(".tool-name, .stack-tool-name, [class*='tool'] h4"):
                name = el.get_text(strip=True)
                if name and len(name) > 1:
                    tools.append(name)

        # Deduplicate preserving order
        seen: set[str] = set()
        unique_tools = []
        for t in tools:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique_tools.append(t)

        return {**base, "found": bool(unique_tools), "tools": unique_tools[:30]}

    except Exception as e:
        console.print(f"[yellow]  StackShare fetch failed: {e}[/yellow]")
        return base
