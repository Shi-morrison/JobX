"""Tests for agents/autofill.py — Playwright calls mocked."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from agents.autofill import (
    detect_ats,
    _build_applicant,
    _find_resume_path,
    _find_cover_letter_path,
)


# ---------------------------------------------------------------------------
# detect_ats
# ---------------------------------------------------------------------------

def test_detect_greenhouse():
    assert detect_ats("https://boards.greenhouse.io/stripe/jobs/12345") == "greenhouse"


def test_detect_greenhouse_job_boards():
    assert detect_ats("https://job-boards.greenhouse.io/acme/jobs/99") == "greenhouse"


def test_detect_lever():
    assert detect_ats("https://jobs.lever.co/stripe/abc-123") == "lever"


def test_detect_workday():
    assert detect_ats("https://stripe.myworkdayjobs.com/en-US/External/job/...") == "workday"


def test_detect_linkedin():
    assert detect_ats("https://www.linkedin.com/jobs/view/123456") == "linkedin"


def test_detect_unknown():
    assert detect_ats("https://careers.stripe.com/jobs/123") is None


def test_detect_case_insensitive():
    assert detect_ats("https://boards.Greenhouse.io/Acme/jobs/1") == "greenhouse"


# ---------------------------------------------------------------------------
# _build_applicant
# ---------------------------------------------------------------------------

def _make_job(title="Software Engineer", company="Stripe", url="https://jobs.lever.co/stripe/1"):
    from db.models import Job
    j = MagicMock(spec=Job)
    j.title = title
    j.company = company
    j.url = url
    return j


def test_build_applicant_full_name():
    job = _make_job()
    resume_data = {
        "personal": {
            "name": "Alice Smith",
            "email": "alice@example.com",
            "phone": "555-1234",
            "linkedin": "https://linkedin.com/in/alice",
        },
        "skills": ["Python", "Go"],
        "experience": [],
    }
    result = _build_applicant(job, resume_data)
    assert result["first_name"] == "Alice"
    assert result["last_name"] == "Smith"
    assert result["name"] == "Alice Smith"
    assert result["email"] == "alice@example.com"
    assert result["company"] == "Stripe"
    assert result["job_title"] == "Software Engineer"
    assert "Python" in result["skills"]


def test_build_applicant_single_name():
    job = _make_job()
    resume_data = {
        "personal": {"name": "Alice"},
        "skills": [],
        "experience": [],
    }
    result = _build_applicant(job, resume_data)
    assert result["first_name"] == "Alice"
    assert result["last_name"] == ""


def test_build_applicant_empty_resume():
    job = _make_job()
    result = _build_applicant(job, {})
    assert result["email"] == ""
    assert result["skills"] == ""


# ---------------------------------------------------------------------------
# _find_resume_path
# ---------------------------------------------------------------------------

def test_find_resume_path_tailored_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tailored = tmp_path / "data" / "resume_versions"
    tailored.mkdir(parents=True)
    (tailored / "resume_12.pdf").write_bytes(b"pdf")

    result = _find_resume_path(12)
    assert result is not None
    assert "resume_12.pdf" in result


def test_find_resume_path_falls_back_to_base(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    (data / "base_resume.pdf").write_bytes(b"pdf")

    result = _find_resume_path(99)
    assert result is not None
    assert "base_resume.pdf" in result


def test_find_resume_path_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    result = _find_resume_path(99)
    assert result is None


# ---------------------------------------------------------------------------
# _find_cover_letter_path
# ---------------------------------------------------------------------------

def test_find_cover_letter_path_docx(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cl_dir = tmp_path / "data" / "cover_letters"
    cl_dir.mkdir(parents=True)
    (cl_dir / "cover_letter_5.docx").write_bytes(b"docx")

    result = _find_cover_letter_path(5)
    assert result is not None
    assert "cover_letter_5.docx" in result


def test_find_cover_letter_path_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "cover_letters").mkdir(parents=True)
    result = _find_cover_letter_path(5)
    assert result is None


# ---------------------------------------------------------------------------
# ATS selectors — unit tests for helpers
# ---------------------------------------------------------------------------

def test_greenhouse_selector_lists_non_empty():
    from tools.ats.greenhouse import _FIELD_SELECTORS
    for key, selectors in _FIELD_SELECTORS.items():
        assert len(selectors) > 0, f"No selectors for {key}"


def test_lever_selector_lists_non_empty():
    from tools.ats.lever import _FIELD_SELECTORS
    for key, selectors in _FIELD_SELECTORS.items():
        assert len(selectors) > 0, f"No selectors for {key}"
