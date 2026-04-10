"""Tests for tools/leetcode.py — Task 3.5.1a
Run with: .venv/bin/pytest tests/test_leetcode.py -v
"""
import pytest
from unittest.mock import patch, MagicMock

from tools.leetcode import _company_slug, fetch_company_problems
from agents.interview_prep import _format_leetcode_context


# ---------------------------------------------------------------------------
# _company_slug
# ---------------------------------------------------------------------------

def test_slug_lowercase():
    assert _company_slug("Robinhood") == "robinhood"

def test_slug_spaces_to_hyphens():
    assert _company_slug("Goldman Sachs") == "goldman-sachs"

def test_slug_strips_punctuation():
    assert _company_slug("J.P. Morgan") == "jp-morgan"

def test_slug_already_lowercase():
    assert _company_slug("stripe") == "stripe"

def test_slug_collapses_hyphens():
    assert _company_slug("DoorDash") == "doordash"


# ---------------------------------------------------------------------------
# _format_leetcode_context
# ---------------------------------------------------------------------------

def test_format_not_found():
    result = {"found": False, "problems": []}
    text = _format_leetcode_context(result)
    assert "No LeetCode" in text

def test_format_found_includes_title():
    result = {
        "found": True,
        "window": "three-months",
        "problems": [
            {"title": "Two Sum", "difficulty": "Easy", "url": "https://leetcode.com/problems/two-sum", "frequency": 100.0, "acceptance": 57.1},
            {"title": "Valid Parentheses", "difficulty": "Easy", "url": "https://leetcode.com/problems/valid-parentheses", "frequency": 80.0, "acceptance": 40.0},
        ],
    }
    text = _format_leetcode_context(result)
    assert "Two Sum" in text
    assert "Easy" in text
    assert "last 3 months" in text

def test_format_empty_problems():
    result = {"found": True, "window": "all", "problems": []}
    text = _format_leetcode_context(result)
    assert "No LeetCode" in text


# ---------------------------------------------------------------------------
# fetch_company_problems
# ---------------------------------------------------------------------------

FAKE_CSV = "ID,URL,Title,Difficulty,Acceptance %,Frequency %\n1,https://leetcode.com/problems/two-sum,Two Sum,Easy,57.1%,100.0%\n3,https://leetcode.com/problems/longest-substring-without-repeating-characters,Longest Substring Without Repeating Characters,Medium,38.5%,62.5%\n"

def _mock_get(url, timeout=10):
    resp = MagicMock()
    if "three-months" in url:
        resp.status_code = 200
        resp.text = FAKE_CSV
        resp.raise_for_status = lambda: None
    elif "contents" in url:
        resp.status_code = 200
        resp.json.return_value = [
            {"name": "stripe", "type": "dir"},
            {"name": "robinhood", "type": "dir"},
            {"name": "google", "type": "dir"},
        ]
        resp.raise_for_status = lambda: None
    else:
        resp.status_code = 404
        resp.raise_for_status = lambda: None
    return resp


def test_fetch_found_company():
    with patch("tools.leetcode.requests.get", side_effect=_mock_get), \
         patch("tools.leetcode._available_companies", None):
        result = fetch_company_problems("Stripe")

    assert result["found"] is True
    assert len(result["problems"]) == 2
    assert result["problems"][0]["title"] == "Two Sum"
    assert result["problems"][0]["difficulty"] == "Easy"
    assert result["problems"][0]["frequency"] == 100.0


def test_fetch_unknown_company():
    with patch("tools.leetcode.requests.get", side_effect=_mock_get), \
         patch("tools.leetcode._available_companies", None):
        result = fetch_company_problems("UnknownCorp XYZ")

    assert result["found"] is False
    assert result["problems"] == []


def test_fetch_respects_limit():
    long_csv = "ID,URL,Title,Difficulty,Acceptance %,Frequency %\n"
    for i in range(30):
        long_csv += f"{i},https://leetcode.com/problems/problem-{i},Problem {i},Easy,50.0%,{100-i}.0%\n"

    def mock_get_long(url, timeout=10):
        resp = MagicMock()
        if "contents" in url:
            resp.status_code = 200
            resp.json.return_value = [{"name": "google", "type": "dir"}]
            resp.raise_for_status = lambda: None
        elif "three-months" in url:
            resp.status_code = 200
            resp.text = long_csv
            resp.raise_for_status = lambda: None
        else:
            resp.status_code = 404
            resp.raise_for_status = lambda: None
        return resp

    with patch("tools.leetcode.requests.get", side_effect=mock_get_long), \
         patch("tools.leetcode._available_companies", None):
        result = fetch_company_problems("Google", limit=10)

    assert result["found"] is True
    assert len(result["problems"]) == 10


def test_fetch_uses_three_months_first():
    with patch("tools.leetcode.requests.get", side_effect=_mock_get), \
         patch("tools.leetcode._available_companies", None):
        result = fetch_company_problems("Robinhood")

    assert result["window"] == "three-months"
