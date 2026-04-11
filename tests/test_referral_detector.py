"""Tests for agents/referral_detector.py — all I/O mocked."""

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import pytest

from agents.referral_detector import (
    _normalize,
    find_referrals,
    load_connections,
)


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------

def test_normalize_basic():
    assert _normalize("Stripe") == "stripe"


def test_normalize_strips_inc():
    assert _normalize("Stripe, Inc.") == "stripe"


def test_normalize_strips_llc():
    assert _normalize("Acme LLC") == "acme"


def test_normalize_whitespace():
    assert _normalize("  Google  ") == "google"


# ---------------------------------------------------------------------------
# find_referrals
# ---------------------------------------------------------------------------

CONNECTIONS = [
    {"name": "Alice Smith", "company": "Stripe, Inc.", "position": "Engineer", "url": "https://li/alice", "email": ""},
    {"name": "Bob Jones",   "company": "Google LLC",   "position": "PM",        "url": "https://li/bob",   "email": ""},
    {"name": "Carol Lee",   "company": "Stripe",       "position": "Recruiter", "url": "https://li/carol", "email": "carol@stripe.com"},
    {"name": "Dan White",   "company": "",             "position": "",          "url": "",                 "email": ""},
]


def test_find_referrals_exact_match():
    matches = find_referrals("Stripe", CONNECTIONS)
    names = [m["name"] for m in matches]
    assert "Alice Smith" in names
    assert "Carol Lee" in names
    assert "Bob Jones" not in names


def test_find_referrals_case_insensitive():
    matches = find_referrals("stripe", CONNECTIONS)
    assert len(matches) == 2


def test_find_referrals_no_match():
    matches = find_referrals("OpenAI", CONNECTIONS)
    assert matches == []


def test_find_referrals_skips_empty_company():
    matches = find_referrals("", CONNECTIONS)
    assert all(m["company"] for m in matches)


def test_find_referrals_partial_match():
    # "Google" should match "Google LLC"
    matches = find_referrals("Google", CONNECTIONS)
    assert len(matches) == 1
    assert matches[0]["name"] == "Bob Jones"


# ---------------------------------------------------------------------------
# load_connections
# ---------------------------------------------------------------------------

LINKEDIN_CSV = """Notes:
:
First Name,Last Name,URL,Email Address,Company,Position,Connected On
Alice,Smith,https://li/alice,,Stripe,Engineer,01 Jan 2024
Bob,Jones,https://li/bob,,Google,PM,02 Jan 2024
"""


def test_load_connections_parses_csv(tmp_path):
    csv_file = tmp_path / "connections.csv"
    csv_file.write_text(LINKEDIN_CSV, encoding="utf-8")

    result = load_connections(csv_path=csv_file)

    assert len(result) == 2
    assert result[0]["name"] == "Alice Smith"
    assert result[0]["company"] == "Stripe"
    assert result[1]["name"] == "Bob Jones"


def test_load_connections_missing_file(tmp_path):
    result = load_connections(csv_path=tmp_path / "nonexistent.csv")
    assert result == []


def test_load_connections_empty_csv(tmp_path):
    csv_file = tmp_path / "connections.csv"
    csv_file.write_text("First Name,Last Name,URL,Email Address,Company,Position,Connected On\n")
    result = load_connections(csv_path=csv_file)
    assert result == []
