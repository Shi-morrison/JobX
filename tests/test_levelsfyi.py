"""Tests for tools/levelsfyi.py — all HTTP calls mocked."""

from unittest.mock import MagicMock, patch

from tools.levelsfyi import (
    _company_slug,
    _parse_markdown,
    fetch_levelsfyi_compensation,
)
from agents.interview_prep import _format_compensation_context

# ---------------------------------------------------------------------------
# Sample markdown that mirrors the real levels.fyi response format
# ---------------------------------------------------------------------------

_SAMPLE_MD = """# Levels.fyi – Google Salaries

**URL:** https://www.levels.fyi/companies/google/salaries
**Generated:** 2026-04-10T18:34:08.711Z
**Scope:** All roles at Google
**Location:** United States
**Currency:** USD ($)

---
## Aggregate Highlights
- Median Total Compensation (All Roles): $296,944
- Last Updated: April 10, 2026

---
## Key Breakdowns

### Job Families
| Rank | Job Family | Median Total Compensation |
| --- | --- | --- |
| 1 | Software Engineer | $606,020 |
| 2 | Product Manager | $454,377 |
| 3 | Software Engineering Manager | $780,247 |
| 4 | Data Scientist | $412,583 |
"""


# ---------------------------------------------------------------------------
# _company_slug
# ---------------------------------------------------------------------------

def test_slug_simple():
    assert _company_slug("Google") == "google"


def test_slug_spaces():
    assert _company_slug("Goldman Sachs") == "goldman-sachs"


def test_slug_punctuation():
    assert _company_slug("J.P. Morgan") == "jp-morgan"


def test_slug_mixed_case():
    assert _company_slug("Robinhood") == "robinhood"


# ---------------------------------------------------------------------------
# _parse_markdown
# ---------------------------------------------------------------------------

def test_parse_median_total_comp():
    result = _parse_markdown(_SAMPLE_MD)
    assert result["median_total_comp"] == "$296,944"


def test_parse_software_engineer_median():
    result = _parse_markdown(_SAMPLE_MD)
    assert result["software_engineer_median"] == "$606,020"


def test_parse_job_families():
    result = _parse_markdown(_SAMPLE_MD)
    assert len(result["job_families"]) >= 3
    assert result["job_families"][0]["role"] == "Software Engineer"
    assert result["job_families"][0]["median"] == "$606,020"


def test_parse_empty_markdown():
    result = _parse_markdown("")
    assert result["median_total_comp"] == ""
    assert result["job_families"] == []


# ---------------------------------------------------------------------------
# fetch_levelsfyi_compensation
# ---------------------------------------------------------------------------

def _mock_response(status: int, text: str = "") -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.text = text
    return m


def test_fetch_found():
    with patch("tools.levelsfyi.requests.get", return_value=_mock_response(200, _SAMPLE_MD)):
        result = fetch_levelsfyi_compensation("Google")

    assert result["found"] is True
    assert result["company_slug"] == "google"
    assert "levels.fyi" in result["url"]
    assert result["median_total_comp"] == "$296,944"
    assert result["software_engineer_median"] == "$606,020"


def test_fetch_404():
    with patch("tools.levelsfyi.requests.get", return_value=_mock_response(404)):
        result = fetch_levelsfyi_compensation("UnknownCorp")

    assert result["found"] is False
    assert result["median_total_comp"] == ""


def test_fetch_request_error():
    with patch("tools.levelsfyi.requests.get", side_effect=Exception("timeout")):
        result = fetch_levelsfyi_compensation("Stripe")

    assert result["found"] is False


def test_fetch_url_uses_slug():
    with patch("tools.levelsfyi.requests.get", return_value=_mock_response(404)):
        result = fetch_levelsfyi_compensation("Goldman Sachs")
    assert "goldman-sachs" in result["url"]


# ---------------------------------------------------------------------------
# _format_compensation_context
# ---------------------------------------------------------------------------

def test_format_not_found():
    result = _format_compensation_context({"found": False})
    assert "No levels.fyi" in result


def test_format_found():
    comp = {
        "found": True,
        "median_total_comp": "$296,944",
        "software_engineer_median": "$606,020",
        "job_families": [
            {"role": "Software Engineer", "median": "$606,020"},
            {"role": "Product Manager", "median": "$454,377"},
        ],
    }
    result = _format_compensation_context(comp)
    assert "$296,944" in result
    assert "$606,020" in result
    assert "Software Engineer" in result
