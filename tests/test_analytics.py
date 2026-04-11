"""Tests for agents/analytics.py and agents/digest.py — all DB calls mocked."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest

from agents.analytics import (
    compute_pipeline_stats,
    compute_outreach_stats,
    compute_top_segments,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(fit_score=None, status="new", company="Stripe"):
    from db.models import Job
    j = MagicMock(spec=Job)
    j.fit_score = fit_score
    j.status = status
    j.company = company
    j.id = 1
    j.title = "Software Engineer"
    j.created_at = datetime.utcnow()
    return j


def _make_sequence(status="sent", response_received=False, follow_up_due=None):
    from db.models import OutreachSequence
    s = MagicMock(spec=OutreachSequence)
    s.status = status
    s.response_received = response_received
    s.follow_up_due = follow_up_due or (datetime.utcnow() - timedelta(days=1))
    s.sent_at = datetime.utcnow() - timedelta(days=6)
    return s


def _make_outcome(job_id=1, stage="technical"):
    from db.models import InterviewOutcome
    o = MagicMock(spec=InterviewOutcome)
    o.job_id = job_id
    o.stage_reached = stage
    return o


# ---------------------------------------------------------------------------
# compute_pipeline_stats
# ---------------------------------------------------------------------------

def test_pipeline_stats_empty():
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.all.return_value = []

    with patch("agents.analytics.get_session", return_value=mock_db):
        result = compute_pipeline_stats()

    assert result["total_jobs_in_db"] == 0
    assert result["scored"] == 0
    assert result["applied"] == 0
    assert result["avg_fit_score"] == 0


def test_pipeline_stats_with_data():
    jobs = [
        _make_job(fit_score=8.0, status="applied"),
        _make_job(fit_score=7.0, status="new"),
        _make_job(fit_score=None, status="new"),
    ]
    outcomes = [_make_outcome(stage="technical")]

    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)

    def query_side(model):
        from db.models import Job, InterviewOutcome
        q = MagicMock()
        if model is Job:
            q.all.return_value = jobs
        elif model is InterviewOutcome:
            q.all.return_value = outcomes
        return q

    mock_db.query.side_effect = query_side

    with patch("agents.analytics.get_session", return_value=mock_db):
        result = compute_pipeline_stats()

    assert result["total_jobs_in_db"] == 3
    assert result["scored"] == 2
    assert result["applied"] == 1
    assert result["avg_fit_score"] == 7.5
    assert result["outcome_stages"]["technical"] == 1


# ---------------------------------------------------------------------------
# compute_outreach_stats
# ---------------------------------------------------------------------------

def test_outreach_stats_empty():
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.all.return_value = []

    with patch("agents.analytics.get_session", return_value=mock_db):
        result = compute_outreach_stats()

    assert result["total_sequences"] == 0
    assert result["response_rate_pct"] == 0


def test_outreach_stats_with_data():
    seqs = [
        _make_sequence(status="sent", response_received=False),
        _make_sequence(status="responded", response_received=True),
        _make_sequence(status="ghosted", response_received=False),
        _make_sequence(status="pending", response_received=False),
    ]
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.all.return_value = seqs

    with patch("agents.analytics.get_session", return_value=mock_db):
        result = compute_outreach_stats()

    assert result["total_sequences"] == 4
    assert result["sent"] == 3  # sent + responded + ghosted
    assert result["responded"] == 1
    assert result["pending"] == 1
    assert result["response_rate_pct"] == pytest.approx(33.3, abs=0.1)


# ---------------------------------------------------------------------------
# compute_top_segments
# ---------------------------------------------------------------------------

def test_top_segments_empty():
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)

    def query_side(model):
        from db.models import Job, InterviewOutcome
        q = MagicMock()
        q.filter.return_value.all.return_value = []
        q.all.return_value = []
        return q

    mock_db.query.side_effect = query_side

    with patch("agents.analytics.get_session", return_value=mock_db):
        result = compute_top_segments()

    assert isinstance(result, list)
    assert len(result) == 4  # always 4 buckets


def test_top_segments_bucketing():
    jobs = [
        _make_job(fit_score=9.5, status="applied"),
        _make_job(fit_score=7.5, status="new"),
        _make_job(fit_score=5.0, status="new"),
        _make_job(fit_score=3.0, status="new"),
    ]
    outcomes = []

    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)

    def query_side(model):
        from db.models import Job, InterviewOutcome
        q = MagicMock()
        if model is Job:
            q.filter.return_value.all.return_value = jobs
        elif model is InterviewOutcome:
            q.all.return_value = outcomes
        return q

    mock_db.query.side_effect = query_side

    with patch("agents.analytics.get_session", return_value=mock_db):
        result = compute_top_segments()

    # One job per bucket
    totals = {s["segment"]: s["total"] for s in result}
    assert totals["9-10 (high fit)"] == 1
    assert totals["7-8 (good fit)"] == 1
    assert totals["5-6 (okay fit)"] == 1
    assert totals["1-4 (low fit)"] == 1


# ---------------------------------------------------------------------------
# digest helpers
# ---------------------------------------------------------------------------

def test_pipeline_summary_counts():
    from agents.digest import _pipeline_summary
    jobs = [
        _make_job(fit_score=8.0, status="applied"),
        _make_job(fit_score=7.0, status="applied"),
        _make_job(fit_score=None, status="new"),
        _make_job(fit_score=9.0, status="interviewing"),
    ]
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.all.return_value = jobs

    with patch("agents.digest.get_session", return_value=mock_db):
        result = _pipeline_summary()

    assert result["applied"] == 2
    assert result["interviewing"] == 1


def test_due_followups_count():
    from agents.digest import _due_followups_count
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.filter.return_value.count.return_value = 3

    with patch("agents.digest.get_session", return_value=mock_db):
        result = _due_followups_count()

    assert result == 3


def test_study_items_no_prep():
    from agents.digest import _study_items
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.order_by.return_value.first.return_value = None

    with patch("agents.digest.get_session", return_value=mock_db):
        result = _study_items()

    assert result == []


def test_study_items_with_plan():
    from agents.digest import _study_items
    from db.models import InterviewPrep
    prep = MagicMock(spec=InterviewPrep)
    prep.study_plan = [
        {"topic": "System Design: consistent hashing", "hours": 3},
        {"topic": "Dynamic Programming", "hours": 5},
    ]
    prep.created_at = datetime.utcnow()

    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)
    mock_db.query.return_value.order_by.return_value.first.return_value = prep

    with patch("agents.digest.get_session", return_value=mock_db):
        result = _study_items()

    assert len(result) == 2
    assert "System Design" in result[0]
