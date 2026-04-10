"""Glassdoor interview review scraper.

Uses Playwright to render the JS-heavy interview page and extract reported
questions before the login wall. Typically yields 5–15 questions per company.
"""

import asyncio
import random
import re
import requests
from urllib.parse import quote

from rich.console import Console

console = Console()

_GLASSDOOR_BASE = "https://www.glassdoor.com"
_TYPEAHEAD_URL = (
    "https://www.glassdoor.com/searchsuggest/typeahead"
    "?query={query}&locationId=0&locationType=N&numSuggestions=5&source=GD_JSON"
)
_INTERVIEW_URL = (
    "https://www.glassdoor.com/Interview/{slug}-Interview-Questions-E{employer_id}.htm"
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.glassdoor.com/",
}

# Selectors tried in order — Glassdoor renames classes often but data-test attrs
# are more stable. The list covers old and new site versions.
_CARD_SELECTORS = [
    "[data-test='InterviewQuestion']",
    "[data-test='interview-question-item']",
    "li.interview-question",
    "[class*='InterviewQuestion']",
    "[class*='interviewQuestion']",
    "article[class*='interview']",
]
_QUESTION_SELECTORS = [
    "[data-test='question-text']",
    "[class*='questionText']",
    "[class*='question-text']",
    "[class*='QuestionText']",
    "p",
]
_DIFFICULTY_SELECTORS = [
    "[data-test='difficulty']",
    "[class*='difficulty']",
    "[class*='Difficulty']",
]
_OUTCOME_SELECTORS = [
    "[data-test='outcome']",
    "[class*='outcome']",
    "[class*='Outcome']",
    "[class*='result']",
]
# Popups/modals to dismiss before scraping
_DISMISS_SELECTORS = [
    "[data-test='cookieConsent-accept']",
    "#onetrust-accept-btn-handler",
    "[aria-label='Close']",
    ".modal-exit",
    "[data-test='modal-close']",
    "button[class*='CloseButton']",
    "button[class*='close']",
]


def _company_slug(name: str) -> str:
    """Normalize company name to a Glassdoor URL slug."""
    slug = name.strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def _find_employer_id(company_name: str) -> tuple[str | None, str]:
    """Look up Glassdoor employer ID via typeahead API.

    Returns (employer_id, slug). employer_id may be None if not found.
    """
    url = _TYPEAHEAD_URL.format(query=quote(company_name))
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        if resp.status_code == 200:
            items = resp.json()
            for item in items:
                eid = (
                    item.get("employerId")
                    or item.get("id")
                    or item.get("employer_id")
                )
                label = (
                    item.get("label")
                    or item.get("suggestion")
                    or item.get("name")
                    or company_name
                )
                if eid:
                    return str(eid), _company_slug(str(label))
    except Exception:
        pass
    return None, _company_slug(company_name)


async def _scrape_page(url: str, limit: int) -> list[dict]:
    """Render the Glassdoor interview page with Playwright and extract questions."""
    from playwright.async_api import async_playwright

    questions: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=_UA,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await ctx.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(random.randint(2000, 3500))

            # Dismiss cookie/login popups
            for sel in _DISMISS_SELECTORS:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        await page.wait_for_timeout(400)
                except Exception:
                    pass

            # Find review cards
            cards = []
            for sel in _CARD_SELECTORS:
                found = await page.locator(sel).all()
                if found:
                    cards = found
                    break

            for card in cards[:limit]:
                try:
                    q_text = await _extract_text(card, _QUESTION_SELECTORS, min_len=20)
                    difficulty = await _extract_text(card, _DIFFICULTY_SELECTORS)
                    outcome = await _extract_text(card, _OUTCOME_SELECTORS)

                    if q_text:
                        questions.append({
                            "question": q_text,
                            "difficulty": difficulty,
                            "outcome": outcome,
                        })
                except Exception:
                    continue

        except Exception as e:
            console.print(f"[yellow]  Playwright error: {e}[/yellow]")
        finally:
            await browser.close()

    return questions


async def _extract_text(locator, selectors: list[str], min_len: int = 0) -> str:
    """Try each selector in turn; return first match meeting min_len."""
    for sel in selectors:
        try:
            el = locator.locator(sel).first
            if await el.is_visible(timeout=500):
                text = (await el.inner_text()).strip()
                if len(text) >= min_len:
                    return text
        except Exception:
            pass
    return ""


def fetch_glassdoor_interviews(company_name: str, limit: int = 20) -> dict:
    """Fetch reported interview questions from Glassdoor for a company.

    Looks up the employer ID via typeahead, then renders the interview page
    with Playwright to extract questions visible before the login wall.

    Args:
        company_name: Company name as stored in the job record.
        limit: Max number of questions to return.

    Returns:
        {
            "found": bool,
            "company_slug": str,
            "employer_id": str | None,
            "url": str,
            "questions": [{"question": str, "difficulty": str, "outcome": str}],
        }
    """
    employer_id, slug = _find_employer_id(company_name)

    if employer_id:
        url = _INTERVIEW_URL.format(slug=slug, employer_id=employer_id)
    else:
        url = f"{_GLASSDOOR_BASE}/Interview/{slug}-Interview-Questions.htm"

    try:
        questions = asyncio.run(_scrape_page(url, limit))
    except Exception as e:
        console.print(f"[yellow]  Glassdoor scrape failed: {e}[/yellow]")
        questions = []

    return {
        "found": len(questions) > 0,
        "company_slug": slug,
        "employer_id": employer_id,
        "url": url,
        "questions": questions,
    }
