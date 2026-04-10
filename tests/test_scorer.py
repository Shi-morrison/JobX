"""Tests for agents/scorer.py — run with: .venv/bin/pytest tests/test_scorer.py -v
Covers: fit scorer (2.2), ATS checker (2.3), gap analyzer (2.4)
"""
import pytest
from unittest.mock import patch, MagicMock
from agents.scorer import score_fit, _build_experience_summary
from db.models import Job


# ---------------------------------------------------------------------------
# _build_experience_summary
# ---------------------------------------------------------------------------

def test_build_experience_summary_basic():
    resume_data = {
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Acme",
                "start_date": "Jan 2023",
                "end_date": "Present",
                "bullets": ["Built APIs", "Led team", "Improved latency"],
            }
        ]
    }
    summary = _build_experience_summary(resume_data)
    assert "Software Engineer at Acme" in summary
    assert "Built APIs" in summary


def test_build_experience_summary_caps_bullets():
    """Should only include top 3 bullets per role."""
    resume_data = {
        "experience": [
            {
                "title": "SWE",
                "company": "Corp",
                "start_date": "2022",
                "end_date": "2023",
                "bullets": ["b1", "b2", "b3", "b4", "b5"],
            }
        ]
    }
    summary = _build_experience_summary(resume_data)
    assert "b3" in summary
    assert "b4" not in summary


def test_build_experience_summary_empty():
    assert _build_experience_summary({}) == "No experience listed."
    assert _build_experience_summary({"experience": []}) == "No experience listed."


# ---------------------------------------------------------------------------
# score_fit (mocked Claude)
# ---------------------------------------------------------------------------

def _make_job(title="Software Engineer", company="Acme", description="We need Python and Go skills."):
    job = MagicMock(spec=Job)
    job.id = 1
    job.title = title
    job.company = company
    job.description = description
    return job


RESUME_DATA = {
    "skills": ["Python", "Go", "React"],
    "experience": [
        {
            "title": "SWE",
            "company": "Corp",
            "start_date": "2023",
            "end_date": "Present",
            "bullets": ["Built systems in Go"],
        }
    ],
}


def test_score_fit_returns_valid_score():
    fake_result = {
        "fit_score": 8,
        "matching_skills": ["Python", "Go"],
        "missing_skills": ["Kubernetes"],
        "reasoning": "Strong match on core skills.",
    }
    with patch("agents.scorer.ClaudeClient") as MockClient, \
         patch("agents.scorer.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = fake_result
        result = score_fit(_make_job(), RESUME_DATA)

    assert result["fit_score"] == 8
    assert "Python" in result["matching_skills"]
    assert "Kubernetes" in result["missing_skills"]


def test_score_fit_clamps_score_high():
    """Score above 10 should be clamped to 10."""
    fake_result = {"fit_score": 15, "matching_skills": [], "missing_skills": [], "reasoning": ""}
    with patch("agents.scorer.ClaudeClient") as MockClient, \
         patch("agents.scorer.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = fake_result
        result = score_fit(_make_job(), RESUME_DATA)
    assert result["fit_score"] == 10


def test_score_fit_clamps_score_low():
    """Score below 1 should be clamped to 1."""
    fake_result = {"fit_score": -3, "matching_skills": [], "missing_skills": [], "reasoning": ""}
    with patch("agents.scorer.ClaudeClient") as MockClient, \
         patch("agents.scorer.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = fake_result
        result = score_fit(_make_job(), RESUME_DATA)
    assert result["fit_score"] == 1


def test_score_fit_truncates_long_description():
    """Descriptions over 4000 chars should be truncated before sending."""
    long_desc = "x" * 10000
    captured = {}

    def fake_load_prompt(template_name, **kwargs):
        captured.update(kwargs)
        return "prompt"

    fake_result = {"fit_score": 5, "matching_skills": [], "missing_skills": [], "reasoning": "ok"}
    with patch("agents.scorer.ClaudeClient") as MockClient, \
         patch("agents.scorer.load_prompt", side_effect=fake_load_prompt):
        MockClient.return_value.chat_json.return_value = fake_result
        score_fit(_make_job(description=long_desc), RESUME_DATA)

    assert len(captured["job_description"]) == 4000


# ---------------------------------------------------------------------------
# check_ats (Task 2.3)
# ---------------------------------------------------------------------------

def test_check_ats_returns_score_and_keywords():
    fake_result = {
        "ats_score": 75.0,
        "matched_keywords": ["Python", "Go"],
        "missing_keywords": ["Kubernetes", "Terraform"],
    }
    with patch("agents.scorer.ClaudeClient") as MockClient, \
         patch("agents.scorer.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = fake_result
        from agents.scorer import check_ats
        result = check_ats(_make_job(), RESUME_DATA)

    assert result["ats_score"] == 75.0
    assert "Python" in result["matched_keywords"]
    assert "Kubernetes" in result["missing_keywords"]


def test_check_ats_clamps_score_above_100():
    fake_result = {"ats_score": 120.0, "matched_keywords": [], "missing_keywords": []}
    with patch("agents.scorer.ClaudeClient") as MockClient, \
         patch("agents.scorer.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = fake_result
        from agents.scorer import check_ats
        result = check_ats(_make_job(), RESUME_DATA)
    assert result["ats_score"] == 100.0


def test_check_ats_clamps_score_below_zero():
    fake_result = {"ats_score": -10.0, "matched_keywords": [], "missing_keywords": []}
    with patch("agents.scorer.ClaudeClient") as MockClient, \
         patch("agents.scorer.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = fake_result
        from agents.scorer import check_ats
        result = check_ats(_make_job(), RESUME_DATA)
    assert result["ats_score"] == 0.0


# ---------------------------------------------------------------------------
# analyze_gaps (Task 2.4)
# ---------------------------------------------------------------------------

def test_analyze_gaps_skips_claude_when_no_gaps():
    """If both missing lists are empty, Claude should NOT be called."""
    fit = {"missing_skills": []}
    ats = {"missing_keywords": []}
    with patch("agents.scorer.ClaudeClient") as MockClient:
        from agents.scorer import analyze_gaps
        result = analyze_gaps(fit, ats, RESUME_DATA)
        MockClient.assert_not_called()
    assert result == {"hard_gaps": [], "soft_gaps": [], "reframe_suggestions": []}


def test_analyze_gaps_calls_claude_when_gaps_exist():
    fit = {"missing_skills": ["Kubernetes"]}
    ats = {"missing_keywords": ["Terraform"]}
    fake_result = {
        "hard_gaps": ["Kubernetes"],
        "soft_gaps": ["Terraform"],
        "reframe_suggestions": [{"gap": "Terraform", "suggestion": "Highlight AWS CDK usage"}],
    }
    with patch("agents.scorer.ClaudeClient") as MockClient, \
         patch("agents.scorer.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = fake_result
        from agents.scorer import analyze_gaps
        result = analyze_gaps(fit, ats, RESUME_DATA)

    assert "Kubernetes" in result["hard_gaps"]
    assert "Terraform" in result["soft_gaps"]
    assert result["reframe_suggestions"][0]["gap"] == "Terraform"


def test_analyze_gaps_handles_only_missing_skills():
    """Should call Claude even if only missing_skills is populated."""
    fit = {"missing_skills": ["Rust"]}
    ats = {"missing_keywords": []}
    fake_result = {"hard_gaps": ["Rust"], "soft_gaps": [], "reframe_suggestions": []}
    with patch("agents.scorer.ClaudeClient") as MockClient, \
         patch("agents.scorer.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = fake_result
        from agents.scorer import analyze_gaps
        result = analyze_gaps(fit, ats, RESUME_DATA)
    assert "Rust" in result["hard_gaps"]
