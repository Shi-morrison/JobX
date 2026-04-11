"""Tests for agents/company_research.py and related tools — all external calls mocked."""

from unittest.mock import MagicMock, patch
import pytest

from agents.company_research import (
    _fmt_meta,
    _fmt_rating,
    _fmt_stack,
    _fmt_news,
    _fmt_layoffs,
    get_cached_research,
    research_company,
)


# ---------------------------------------------------------------------------
# Formatter helpers
# ---------------------------------------------------------------------------

def test_fmt_meta_not_found():
    assert _fmt_meta({"found": False}) == "Not found."


def test_fmt_meta_found():
    meta = {
        "found": True,
        "industry": "Fintech",
        "funding_stage": "Series D",
        "estimated_valuation": "$10B",
        "employee_count": "1,000–5,000",
        "description": "Trading app.",
    }
    result = _fmt_meta(meta)
    assert "Fintech" in result
    assert "Series D" in result
    assert "$10B" in result


def test_fmt_rating_not_found():
    assert _fmt_rating({"found": False}) == "Not found."


def test_fmt_rating_found():
    result = _fmt_rating({"found": True, "rating": 3.8, "review_count": "1234"})
    assert "3.8" in result
    assert "1234" in result


def test_fmt_stack_not_found():
    assert _fmt_stack({"found": False, "tools": []}) == "Not found."


def test_fmt_stack_found():
    result = _fmt_stack({"found": True, "tools": ["Python", "Kafka", "PostgreSQL"]})
    assert "Python" in result
    assert "Kafka" in result


def test_fmt_news_empty():
    result = _fmt_news([])
    assert "SerpAPI" in result or "No news" in result


def test_fmt_news_found():
    news = [{"title": "Stripe raises $1B", "url": "https://example.com", "snippet": "Big round."}]
    result = _fmt_news(news)
    assert "Stripe raises $1B" in result


def test_fmt_layoffs_empty():
    assert "No layoff" in _fmt_layoffs([])


def test_fmt_layoffs_found():
    layoffs = [{"title": "Stripe cuts 14%", "url": "https://example.com", "snippet": "Details."}]
    result = _fmt_layoffs(layoffs)
    assert "Stripe cuts 14%" in result


# ---------------------------------------------------------------------------
# get_cached_research
# ---------------------------------------------------------------------------

def test_get_cached_research_miss():
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("agents.company_research.get_session", return_value=mock_db):
        result = get_cached_research("UnknownCorp")
    assert result is None


def test_get_cached_research_hit():
    from db.models import CompanyResearch
    record = MagicMock(spec=CompanyResearch)
    record.company_name = "Stripe"
    record.summary = "Stripe is a payments company."
    record.glassdoor_rating = 4.2
    record.funding_stage = "Private"
    record.employee_count = "4,000+"
    record.industry = "Fintech"
    record.tech_stack = ["Ruby", "Go"]
    record.recent_news = []
    record.layoff_history = []

    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.first.return_value = record

    with patch("agents.company_research.get_session", return_value=mock_db):
        result = get_cached_research("Stripe")

    assert result is not None
    assert result["company_name"] == "Stripe"
    assert result["summary"] == "Stripe is a payments company."
    assert result["glassdoor_rating"] == 4.2


# ---------------------------------------------------------------------------
# research_company — full pipeline mocked
# ---------------------------------------------------------------------------

def _make_db_mock(existing=None):
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.first.return_value = existing
    return mock_db


def test_research_company_uses_cache():
    """If cached record exists and force=False, skip all fetches."""
    from db.models import CompanyResearch
    record = MagicMock(spec=CompanyResearch)
    record.company_name = "Stripe"
    record.summary = "Cached summary."
    record.glassdoor_rating = 4.0
    record.funding_stage = "Private"
    record.employee_count = ""
    record.industry = ""
    record.tech_stack = []
    record.recent_news = []
    record.layoff_history = []

    mock_db = _make_db_mock(existing=record)
    with patch("agents.company_research.get_session", return_value=mock_db):
        result = research_company("Stripe", force=False)

    assert result["summary"] == "Cached summary."


def test_research_company_full_pipeline():
    """Full pipeline with all sources mocked — verifies orchestration."""
    mock_db = _make_db_mock(existing=None)

    with (
        patch("agents.company_research.get_session", return_value=mock_db),
        patch("agents.company_research._fetch_meta", return_value={
            "found": True, "industry": "Fintech", "funding_stage": "Series D",
            "estimated_valuation": "$10B", "employee_count": "2,000", "description": "Payments.",
        }),
        patch("agents.company_research._fetch_rating", return_value={
            "found": True, "rating": 4.1, "review_count": "500",
        }),
        patch("agents.company_research._fetch_stack", return_value={
            "found": True, "tools": ["Python", "Go", "Kafka"],
        }),
        patch("agents.company_research._fetch_news", return_value=[
            {"title": "Stripe raises $1B", "url": "https://x.com", "snippet": "Big round."},
        ]),
        patch("agents.company_research._fetch_layoffs", return_value=[]),
        patch("agents.company_research.ClaudeClient") as MockClaude,
    ):
        MockClaude.return_value.chat_json.return_value = {
            "summary": "Stripe is a leading payments company.",
            "signals": {"growth_stage": "growth", "stability_flag": "stable", "tech_reputation": "strong"},
        }
        result = research_company("Stripe", force=True)

    assert result["company_name"] == "Stripe"
    assert result["glassdoor_rating"] == 4.1
    assert "Python" in result["tech_stack"]
    assert result["summary"] == "Stripe is a leading payments company."
    assert result["signals"]["stability_flag"] == "stable"
