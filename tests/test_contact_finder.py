"""Tests for agents/contact_finder.py — all external calls mocked."""

from unittest.mock import MagicMock, patch
import pytest

from agents.contact_finder import (
    _parse_name_title,
    search_contacts,
    save_contacts,
)


# ---------------------------------------------------------------------------
# _parse_name_title
# ---------------------------------------------------------------------------

def test_parse_name_title_standard():
    name, title = _parse_name_title("Jane Doe - Recruiter at Stripe | LinkedIn", "Stripe")
    assert name == "Jane Doe"
    assert title == "Recruiter"


def test_parse_name_title_no_company_suffix():
    name, title = _parse_name_title("John Smith - Engineering Manager | LinkedIn", "Stripe")
    assert name == "John Smith"
    assert title == "Engineering Manager"


def test_parse_name_title_no_dash():
    name, title = _parse_name_title("Jane Doe | LinkedIn", "Stripe")
    assert name == "Jane Doe"
    assert title == ""


def test_parse_name_title_strips_linkedin():
    name, title = _parse_name_title("Alice Lee - Senior Recruiter · LinkedIn", "Stripe")
    assert name == "Alice Lee"
    assert "LinkedIn" not in title


def test_parse_name_title_empty():
    name, title = _parse_name_title("", "Stripe")
    assert name == ""
    assert title == ""


# ---------------------------------------------------------------------------
# search_contacts
# ---------------------------------------------------------------------------

def test_search_contacts_no_serpapi_key():
    """Returns [] when search_web returns empty (no SERPAPI_KEY)."""
    with patch("tools.search.search_web", return_value=[]):
        result = search_contacts("Stripe", num_results=5)
    assert result == []


def test_search_contacts_deduplicates_urls():
    """Same LinkedIn URL from multiple queries should appear only once."""
    mock_result = [
        {
            "title": "Jane Doe - Recruiter at Stripe | LinkedIn",
            "url": "https://linkedin.com/in/jane-doe",
            "snippet": "Recruiter at Stripe.",
        }
    ]
    with patch("tools.search.search_web", return_value=mock_result):
        result = search_contacts("Stripe", num_results=5)

    # Same URL returned by all 3 queries — should appear once
    urls = [r["linkedin_url"] for r in result]
    assert len(urls) == len(set(urls))


def test_search_contacts_filters_non_linkedin():
    """Non-LinkedIn URLs should be filtered out."""
    mock_results = [
        {"title": "Stripe Careers", "url": "https://stripe.com/jobs", "snippet": ""},
        {"title": "Jane - Recruiter | LinkedIn", "url": "https://linkedin.com/in/jane", "snippet": ""},
    ]
    with patch("tools.search.search_web", return_value=mock_results):
        result = search_contacts("Stripe", num_results=5)
    assert all("linkedin.com/in/" in r["linkedin_url"] for r in result)


# ---------------------------------------------------------------------------
# save_contacts
# ---------------------------------------------------------------------------

def _make_db_mock(existing=None):
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.first.return_value = existing
    return mock_db


def test_save_contacts_inserts_new():
    mock_db = _make_db_mock(existing=None)
    candidates = [
        {
            "name": "Jane Doe",
            "title": "Recruiter",
            "linkedin_url": "https://linkedin.com/in/jane",
            "company": "Stripe",
        }
    ]
    with patch("agents.contact_finder.get_session", return_value=mock_db):
        result = save_contacts(job_id=1, candidates=candidates)
    mock_db.add.assert_called_once()


def test_save_contacts_skips_existing():
    from db.models import Contact
    existing = MagicMock(spec=Contact)
    mock_db = _make_db_mock(existing=existing)
    candidates = [
        {
            "name": "Jane Doe",
            "title": "Recruiter",
            "linkedin_url": "https://linkedin.com/in/jane",
            "company": "Stripe",
        }
    ]
    with patch("agents.contact_finder.get_session", return_value=mock_db):
        result = save_contacts(job_id=1, candidates=candidates)
    mock_db.add.assert_not_called()
    assert len(result) == 1
