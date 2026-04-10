"""Tests for tools/glassdoor.py — all network and Playwright calls mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.glassdoor import (
    _company_slug,
    _find_employer_id,
    fetch_glassdoor_interviews,
)
from agents.interview_prep import _format_glassdoor_context


# ---------------------------------------------------------------------------
# _company_slug
# ---------------------------------------------------------------------------

def test_company_slug_simple():
    assert _company_slug("Google") == "Google"


def test_company_slug_spaces():
    assert _company_slug("Goldman Sachs") == "Goldman-Sachs"


def test_company_slug_punctuation():
    assert _company_slug("J.P. Morgan") == "JP-Morgan"


def test_company_slug_extra_dashes():
    assert _company_slug("  Meta  ") == "Meta"


# ---------------------------------------------------------------------------
# _find_employer_id
# ---------------------------------------------------------------------------

def _make_typeahead_response(employer_id, label):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"employerId": employer_id, "label": label, "suggestion": label}
    ]
    return mock_resp


def test_find_employer_id_found():
    with patch("tools.glassdoor.requests.get", return_value=_make_typeahead_response(9079, "Google")):
        eid, slug = _find_employer_id("Google")
    assert eid == "9079"
    assert slug == "Google"


def test_find_employer_id_not_found():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []  # empty suggestions
    with patch("tools.glassdoor.requests.get", return_value=mock_resp):
        eid, slug = _find_employer_id("UnknownCorp")
    assert eid is None
    assert slug == "UnknownCorp"


def test_find_employer_id_request_error():
    with patch("tools.glassdoor.requests.get", side_effect=Exception("timeout")):
        eid, slug = _find_employer_id("Stripe")
    assert eid is None
    assert slug == "Stripe"


def test_find_employer_id_non_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    with patch("tools.glassdoor.requests.get", return_value=mock_resp):
        eid, slug = _find_employer_id("Airbnb")
    assert eid is None


# ---------------------------------------------------------------------------
# _format_glassdoor_context (lives in agents/interview_prep.py)
# ---------------------------------------------------------------------------


def test_format_glassdoor_context_not_found():
    result = _format_glassdoor_context({"found": False, "questions": []})
    assert "No Glassdoor" in result


def test_format_glassdoor_context_found():
    gd = {
        "found": True,
        "questions": [
            {"question": "How does consistent hashing work?", "difficulty": "Hard", "outcome": "Accepted"},
            {"question": "Design a rate limiter.", "difficulty": "Medium", "outcome": ""},
        ],
    }
    result = _format_glassdoor_context(gd)
    assert "consistent hashing" in result
    assert "rate limiter" in result
    assert "[Hard]" in result
    assert "Accepted" in result


# ---------------------------------------------------------------------------
# fetch_glassdoor_interviews (mocked Playwright)
# ---------------------------------------------------------------------------

def _make_playwright_mock(questions: list[dict]):
    """Build a minimal async Playwright mock that yields the given questions."""

    async def mock_scrape_page(url, limit):
        return questions[:limit]

    return mock_scrape_page


def test_fetch_glassdoor_found():
    questions = [
        {"question": "What is a deadlock?", "difficulty": "Medium", "outcome": "Accepted Offer"},
        {"question": "Explain eventual consistency.", "difficulty": "Hard", "outcome": ""},
    ]
    with (
        patch("tools.glassdoor._find_employer_id", return_value=("9079", "Google")),
        patch("tools.glassdoor._scrape_page", _make_playwright_mock(questions)),
        patch("tools.glassdoor.asyncio.run", side_effect=lambda coro: questions),
    ):
        result = fetch_glassdoor_interviews("Google", limit=10)

    assert result["found"] is True
    assert result["employer_id"] == "9079"
    assert result["company_slug"] == "Google"
    assert "glassdoor.com" in result["url"]
    assert len(result["questions"]) == 2


def test_fetch_glassdoor_not_found():
    with (
        patch("tools.glassdoor._find_employer_id", return_value=(None, "UnknownCorp")),
        patch("tools.glassdoor.asyncio.run", side_effect=lambda coro: []),
    ):
        result = fetch_glassdoor_interviews("UnknownCorp")

    assert result["found"] is False
    assert result["questions"] == []
    assert result["employer_id"] is None


def test_fetch_glassdoor_playwright_exception():
    with (
        patch("tools.glassdoor._find_employer_id", return_value=("123", "Stripe")),
        patch("tools.glassdoor.asyncio.run", side_effect=Exception("browser crash")),
    ):
        result = fetch_glassdoor_interviews("Stripe")

    assert result["found"] is False
    assert result["questions"] == []


def test_fetch_glassdoor_url_with_employer_id():
    with (
        patch("tools.glassdoor._find_employer_id", return_value=("1234", "Meta")),
        patch("tools.glassdoor.asyncio.run", side_effect=lambda coro: []),
    ):
        result = fetch_glassdoor_interviews("Meta")

    assert "E1234" in result["url"]


def test_fetch_glassdoor_url_without_employer_id():
    with (
        patch("tools.glassdoor._find_employer_id", return_value=(None, "TinyStartup")),
        patch("tools.glassdoor.asyncio.run", side_effect=lambda coro: []),
    ):
        result = fetch_glassdoor_interviews("TinyStartup")

    assert "E" not in result["url"]
    assert "TinyStartup" in result["url"]
