"""Tests for agents/hiring_signals.py — all DB calls mocked."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest

from agents.hiring_signals import (
    get_surge_companies,
    get_surge_companies_set,
    is_surge,
    check_hiring_posts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(company: str, title: str = "Software Engineer", days_ago: int = 1) -> MagicMock:
    job = MagicMock()
    job.company = company
    job.title = title
    job.created_at = datetime.utcnow() - timedelta(days=days_ago)
    job.posted_date = datetime.utcnow() - timedelta(days=days_ago)
    return job


def _make_db_mock(jobs: list) -> MagicMock:
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.all.return_value = jobs
    mock_db.query.return_value.filter.return_value.count.return_value = len(jobs)
    return mock_db


# ---------------------------------------------------------------------------
# get_surge_companies
# ---------------------------------------------------------------------------

def test_get_surge_companies_empty_db():
    mock_db = _make_db_mock([])
    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        result = get_surge_companies(days=7, min_jobs=3)
    assert result == []


def test_get_surge_companies_below_threshold():
    """Two jobs from same company — below min_jobs=3 threshold."""
    jobs = [_make_job("Stripe"), _make_job("Stripe")]
    mock_db = _make_db_mock(jobs)
    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        result = get_surge_companies(days=7, min_jobs=3)
    assert result == []


def test_get_surge_companies_single_surge():
    """Exactly 3 jobs from one company — should appear."""
    jobs = [
        _make_job("Stripe", "Backend Engineer"),
        _make_job("Stripe", "Frontend Engineer"),
        _make_job("Stripe", "Platform Engineer"),
    ]
    mock_db = _make_db_mock(jobs)
    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        result = get_surge_companies(days=7, min_jobs=3)
    assert len(result) == 1
    assert result[0]["company"] == "Stripe"
    assert result[0]["job_count"] == 3
    assert len(result[0]["titles"]) == 3


def test_get_surge_companies_multiple_companies():
    """Two companies both surging — sorted by count desc."""
    jobs = (
        [_make_job("Stripe")] * 5 +
        [_make_job("Robinhood")] * 3 +
        [_make_job("Acme")] * 1  # below threshold
    )
    mock_db = _make_db_mock(jobs)
    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        result = get_surge_companies(days=7, min_jobs=3)
    assert len(result) == 2
    assert result[0]["company"] == "Stripe"
    assert result[0]["job_count"] == 5
    assert result[1]["company"] == "Robinhood"
    assert result[1]["job_count"] == 3


def test_get_surge_companies_latest_posted():
    """latest_posted should reflect the most recent posted_date in the group."""
    older = _make_job("Stripe", days_ago=5)
    older.posted_date = datetime.utcnow() - timedelta(days=5)
    newer = _make_job("Stripe", days_ago=1)
    newer.posted_date = datetime.utcnow() - timedelta(days=1)
    third = _make_job("Stripe", days_ago=3)
    third.posted_date = datetime.utcnow() - timedelta(days=3)

    mock_db = _make_db_mock([older, newer, third])
    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        result = get_surge_companies(days=7, min_jobs=3)

    assert len(result) == 1
    latest = result[0]["latest_posted"]
    assert abs((latest - newer.posted_date).total_seconds()) < 2


def test_get_surge_companies_no_posted_date():
    """Jobs with no posted_date should still be counted; latest_posted stays None."""
    jobs = [_make_job("Acme")] * 3
    for j in jobs:
        j.posted_date = None
    mock_db = _make_db_mock(jobs)
    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        result = get_surge_companies(days=7, min_jobs=3)
    assert len(result) == 1
    assert result[0]["latest_posted"] is None


# ---------------------------------------------------------------------------
# get_surge_companies_set
# ---------------------------------------------------------------------------

def test_get_surge_companies_set_returns_set():
    jobs = [_make_job("Stripe")] * 4
    mock_db = _make_db_mock(jobs)
    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        result = get_surge_companies_set(days=7, min_jobs=3)
    assert isinstance(result, set)
    assert "Stripe" in result


def test_get_surge_companies_set_empty():
    mock_db = _make_db_mock([])
    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        result = get_surge_companies_set()
    assert result == set()


# ---------------------------------------------------------------------------
# is_surge
# ---------------------------------------------------------------------------

def test_is_surge_true():
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.count.return_value = 4

    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        assert is_surge("Stripe", days=7, min_jobs=3) is True


def test_is_surge_false():
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.count.return_value = 2

    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        assert is_surge("Stripe", days=7, min_jobs=3) is False


def test_is_surge_exact_threshold():
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.count.return_value = 3

    with patch("agents.hiring_signals.get_session", return_value=mock_db):
        assert is_surge("Stripe", days=7, min_jobs=3) is True


# ---------------------------------------------------------------------------
# check_hiring_posts (SerpAPI — optional)
# ---------------------------------------------------------------------------

def test_check_hiring_posts_no_key():
    """Returns [] when search_web returns empty (no SERPAPI_KEY)."""
    with patch("tools.search.search_web", return_value=[]):
        result = check_hiring_posts("Stripe")
    assert result == []


def test_check_hiring_posts_returns_results():
    mock_results = [
        {"title": "Stripe is hiring!", "url": "https://linkedin.com/...", "snippet": "Join our team."}
    ]
    with patch("agents.hiring_signals.check_hiring_posts", return_value=mock_results) as mock_fn:
        result = mock_fn("Stripe")
    assert len(result) == 1
    assert "Stripe is hiring!" in result[0]["title"]


def test_check_hiring_posts_exception_returns_empty():
    """If search_web raises, return [] gracefully."""
    with patch("tools.search.search_web", side_effect=Exception("network error")):
        result = check_hiring_posts("Stripe")
    assert result == []
