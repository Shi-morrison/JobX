"""Tests for agents/salary_intel.py — all external calls mocked."""

from unittest.mock import MagicMock, patch
import pytest

from agents.salary_intel import (
    _fmt_salary,
    get_cached_salary,
    fetch_salary_data,
    _record_to_dict,
)


# ---------------------------------------------------------------------------
# _fmt_salary
# ---------------------------------------------------------------------------

def test_fmt_salary_none():
    assert _fmt_salary(None) == "—"


def test_fmt_salary_integer():
    assert _fmt_salary(200000) == "$200,000"


def test_fmt_salary_small():
    assert _fmt_salary(0) == "$0"


# ---------------------------------------------------------------------------
# _record_to_dict
# ---------------------------------------------------------------------------

def test_record_to_dict():
    from db.models import SalaryData
    record = MagicMock(spec=SalaryData)
    record.company_name = "Stripe"
    record.role_level = "senior"
    record.salary_min = 180000
    record.salary_max = 280000
    record.equity = "RSUs, 4-year vest"
    record.source = "levels.fyi"

    result = _record_to_dict(record)
    assert result["company_name"] == "Stripe"
    assert result["role_level"] == "senior"
    assert result["salary_min"] == 180000
    assert result["salary_max"] == 280000
    assert result["equity"] == "RSUs, 4-year vest"
    assert result["found"] is True


def test_record_to_dict_no_equity():
    from db.models import SalaryData
    record = MagicMock(spec=SalaryData)
    record.company_name = "Acme"
    record.role_level = "mid"
    record.salary_min = None
    record.salary_max = None
    record.equity = None
    record.source = "levels.fyi"

    result = _record_to_dict(record)
    assert result["equity"] == ""


# ---------------------------------------------------------------------------
# get_cached_salary
# ---------------------------------------------------------------------------

def _make_db_mock(existing=None):
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.first.return_value = existing
    return mock_db


def test_get_cached_salary_miss():
    mock_db = _make_db_mock(existing=None)
    with patch("agents.salary_intel.get_session", return_value=mock_db):
        result = get_cached_salary("UnknownCorp", "senior")
    assert result is None


def test_get_cached_salary_hit():
    from db.models import SalaryData
    record = MagicMock(spec=SalaryData)
    record.company_name = "Stripe"
    record.role_level = "senior"
    record.salary_min = 200000
    record.salary_max = 320000
    record.equity = "RSUs"
    record.source = "levels.fyi"

    mock_db = _make_db_mock(existing=record)
    with patch("agents.salary_intel.get_session", return_value=mock_db):
        result = get_cached_salary("Stripe", "senior")

    assert result is not None
    assert result["salary_min"] == 200000
    assert result["salary_max"] == 320000
    assert result["found"] is True


# ---------------------------------------------------------------------------
# fetch_salary_data
# ---------------------------------------------------------------------------

def test_fetch_salary_uses_cache():
    """If cached record exists and force=False, skip all fetches."""
    from db.models import SalaryData
    record = MagicMock(spec=SalaryData)
    record.company_name = "Stripe"
    record.role_level = "senior"
    record.salary_min = 190000
    record.salary_max = 290000
    record.equity = "RSUs"
    record.source = "levels.fyi"

    mock_db = _make_db_mock(existing=record)
    with patch("agents.salary_intel.get_session", return_value=mock_db):
        result = fetch_salary_data("Stripe", "senior", force=False)

    assert result["salary_min"] == 190000
    assert result["found"] is True


def test_fetch_salary_no_levels_data():
    """When levels.fyi returns found=False, return found=False without calling Claude."""
    mock_db = _make_db_mock(existing=None)

    with (
        patch("agents.salary_intel.get_session", return_value=mock_db),
        patch("agents.salary_intel.fetch_salary_data.__wrapped__", create=True),
        patch("tools.levelsfyi.fetch_levelsfyi_compensation", return_value={
            "found": False, "median_total_comp": "", "job_families": [], "raw_summary": "",
        }),
        patch("agents.salary_intel.ClaudeClient") as MockClaude,
    ):
        # Patch the import inside the function
        with patch.dict("sys.modules", {}):
            import agents.salary_intel as mod
            with patch.object(mod, "fetch_salary_data", wraps=mod.fetch_salary_data):
                pass

        # Direct approach: patch the levelsfyi module via its import path inside the agent
        with patch("agents.salary_intel.get_session", return_value=mock_db):
            from unittest.mock import patch as p2
            with p2("tools.levelsfyi.fetch_levelsfyi_compensation", return_value={
                "found": False, "median_total_comp": "", "job_families": [], "raw_summary": "",
            }):
                result = fetch_salary_data("SmallCorp", "senior", force=True)

    assert result["found"] is False
    MockClaude.assert_not_called()


def test_fetch_salary_full_pipeline():
    """Full pipeline: levels data found, Claude extracts range, saved to DB."""
    mock_db = _make_db_mock(existing=None)

    comp_data = {
        "found": True,
        "median_total_comp": "$296,000",
        "software_engineer_median": "$350,000",
        "job_families": [
            {"role": "Software Engineer", "median": "$280,000"},
            {"role": "Senior Software Engineer", "median": "$380,000"},
            {"role": "Staff Engineer", "median": "$480,000"},
        ],
        "raw_summary": "Stripe is a payments company with median TC of $296k.",
    }

    with (
        patch("agents.salary_intel.get_session", return_value=mock_db),
        patch("agents.salary_intel.ClaudeClient") as MockClaude,
    ):
        MockClaude.return_value.chat_json.return_value = {
            "salary_min": 304000,
            "salary_max": 456000,
            "equity_range": "RSUs, 4-year vest with 1-year cliff",
            "matched_role": "Senior Software Engineer",
            "notes": "Range based on Senior SWE median ±20%.",
        }

        with patch("tools.levelsfyi.fetch_levelsfyi_compensation", return_value=comp_data):
            result = fetch_salary_data("Stripe", "senior", force=True)

    assert result["found"] is True
    assert result["salary_min"] == 304000
    assert result["salary_max"] == 456000
    assert result["equity"] == "RSUs, 4-year vest with 1-year cliff"
    assert result["matched_role"] == "Senior Software Engineer"
    assert result["company_name"] == "Stripe"
    assert result["role_level"] == "senior"
    assert len(result["all_levels"]) == 3


def test_fetch_salary_normalizes_level():
    """Level string is lowercased and stripped."""
    mock_db = _make_db_mock(existing=None)

    comp_data = {
        "found": True,
        "median_total_comp": "$200,000",
        "software_engineer_median": "",
        "job_families": [{"role": "Software Engineer", "median": "$200,000"}],
        "raw_summary": "",
    }

    with (
        patch("agents.salary_intel.get_session", return_value=mock_db),
        patch("agents.salary_intel.ClaudeClient") as MockClaude,
    ):
        MockClaude.return_value.chat_json.return_value = {
            "salary_min": 160000,
            "salary_max": 240000,
            "equity_range": "",
            "matched_role": "Software Engineer",
            "notes": "",
        }

        with patch("tools.levelsfyi.fetch_levelsfyi_compensation", return_value=comp_data):
            result = fetch_salary_data("Acme", "  MID  ", force=True)

    assert result["role_level"] == "mid"
