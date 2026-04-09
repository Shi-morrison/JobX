"""Tests for tools/scraper.py — run with: .venv/bin/pytest tests/test_scraper.py -v"""
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

from db.session import init_db, get_session
from db.models import Job


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def in_memory_db(tmp_path, monkeypatch):
    """Redirect the DB to a temp file for every test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("config.settings.db_path", str(db_file))
    monkeypatch.setattr("db.session.engine", __import__("sqlalchemy").create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    ))
    # Recreate SessionLocal bound to new engine
    from sqlalchemy.orm import sessionmaker
    new_session = sessionmaker(bind=__import__("db.session", fromlist=["engine"]).engine, autocommit=False, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr("db.session.SessionLocal", new_session)
    init_db()


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    f = tmp_path / "scraper_state.json"
    monkeypatch.setattr("tools.scraper._STATE_FILE", f)
    return f


# ---------------------------------------------------------------------------
# _is_target_role
# ---------------------------------------------------------------------------

def test_is_target_role_match(monkeypatch):
    monkeypatch.setattr("config.settings.target_roles", ["Software Engineer", "Backend Engineer"])
    from tools.scraper import _is_target_role
    assert _is_target_role("Senior Software Engineer") is True
    assert _is_target_role("Backend Engineer II") is True


def test_is_target_role_no_match(monkeypatch):
    monkeypatch.setattr("config.settings.target_roles", ["Software Engineer"])
    from tools.scraper import _is_target_role
    assert _is_target_role("Product Manager") is False
    assert _is_target_role("Sales Executive") is False


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def test_load_state_missing_file(state_file):
    from tools.scraper import _load_state
    assert _load_state() == {}


def test_save_and_load_state(state_file):
    from tools.scraper import _load_state, _save_state
    _save_state({"last_scraped_at": "2025-01-01T00:00:00+00:00"})
    state = _load_state()
    assert state["last_scraped_at"] == "2025-01-01T00:00:00+00:00"


def test_hours_since_last_scrape_none():
    from tools.scraper import _hours_since_last_scrape
    assert _hours_since_last_scrape({}) is None


def test_hours_since_last_scrape_value():
    from tools.scraper import _hours_since_last_scrape
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    hours = _hours_since_last_scrape({"last_scraped_at": two_hours_ago})
    assert 1.9 < hours < 2.1


# ---------------------------------------------------------------------------
# _insert_new_jobs
# ---------------------------------------------------------------------------

def test_insert_new_jobs_basic(monkeypatch):
    monkeypatch.setattr("config.settings.target_roles", ["Software Engineer"])
    from tools.scraper import _insert_new_jobs
    jobs = [{"title": "Software Engineer", "company": "Acme", "url": "https://example.com/1",
              "description": "Great job", "source": "linkedin", "posted_date": None}]
    inserted = _insert_new_jobs(jobs)
    assert len(inserted) == 1
    assert inserted[0].title == "Software Engineer"


def test_insert_new_jobs_deduplication(monkeypatch):
    monkeypatch.setattr("config.settings.target_roles", ["Software Engineer"])
    from tools.scraper import _insert_new_jobs
    job = {"title": "Software Engineer", "company": "Acme", "url": "https://example.com/1",
            "description": "desc", "source": "indeed", "posted_date": None}
    _insert_new_jobs([job])
    # Insert same URL a second time
    inserted = _insert_new_jobs([job])
    assert len(inserted) == 0


def test_insert_new_jobs_filters_non_target_roles(monkeypatch):
    monkeypatch.setattr("config.settings.target_roles", ["Software Engineer"])
    from tools.scraper import _insert_new_jobs
    jobs = [{"title": "Product Manager", "company": "Acme", "url": "https://example.com/pm",
              "description": "PM role", "source": "linkedin", "posted_date": None}]
    inserted = _insert_new_jobs(jobs)
    assert len(inserted) == 0


def test_insert_new_jobs_dedupes_within_batch(monkeypatch):
    monkeypatch.setattr("config.settings.target_roles", ["Software Engineer"])
    from tools.scraper import _insert_new_jobs
    job = {"title": "Software Engineer", "company": "Acme", "url": "https://example.com/1",
            "description": "desc", "source": "indeed", "posted_date": None}
    # Same job twice in the same batch
    inserted = _insert_new_jobs([job, job])
    assert len(inserted) == 1
