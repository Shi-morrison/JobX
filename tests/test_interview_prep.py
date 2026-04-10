"""Tests for agents/interview_prep.py — Tasks 3.5.2–3.5.6
Run with: .venv/bin/pytest tests/test_interview_prep.py -v
"""
import pytest
from unittest.mock import patch, MagicMock

from agents.interview_prep import (
    generate_technical_questions,
    generate_behavioral_questions,
    generate_company_questions,
    generate_study_plan,
    _build_question_pool,
    _score_answer,
)
from db.models import Job, InterviewPrep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(id=1, title="Backend Engineer", company="Stripe",
               description="We need Python, Go, and Kubernetes.", fit_score=8.0):
    job = MagicMock(spec=Job)
    job.id = id
    job.title = title
    job.company = company
    job.description = description
    job.fit_score = fit_score
    job.gap_analysis = {
        "hard_gaps": ["Kubernetes"],
        "soft_gaps": ["distributed systems"],
        "reframe_suggestions": [{"gap": "distributed systems", "suggestion": "Highlight microservices"}],
    }
    return job


RESUME_DATA = {
    "skills": ["Python", "Go", "PostgreSQL"],
    "experience": [
        {
            "title": "Software Engineer",
            "company": "Corp",
            "start_date": "2023",
            "end_date": "Present",
            "bullets": ["Built APIs in Python", "Led backend team"],
        }
    ],
}

FAKE_TECHNICAL = {
    "technical_questions": {
        "Python": ["What is the GIL?", "Explain asyncio.", "How do you profile Python code?"],
        "Kubernetes": ["What is a pod?", "How do deployments work?"],
    }
}

FAKE_BEHAVIORAL = {
    "behavioral_questions": [
        {
            "question": "Tell me about a time you led a project under pressure.",
            "trait": "ownership",
            "star_framework": "Situation: ... Task: ... Action: ... Result: ...",
        },
        {
            "question": "Describe a disagreement with a teammate.",
            "trait": "collaboration",
            "star_framework": "Situation: ... Task: ... Action: ... Result: ...",
        },
    ]
}

FAKE_COMPANY = {
    "company_questions": [
        {"question": "What does the on-call rotation look like?", "talking_point": "Shows you think about operational realities."},
        {"question": "How do you balance speed vs. reliability?", "talking_point": "Probes engineering culture."},
    ],
    "why_us_talking_points": [
        "Stripe's API design is industry-leading — I've built against it and want to contribute to that standard.",
        "The scale of Stripe's payment infrastructure is a unique engineering challenge.",
    ],
}

FAKE_STUDY_PLAN = {
    "study_plan": [
        {
            "topic": "Kubernetes",
            "priority": "high",
            "resources": ["kubernetes.io/docs", "Kubernetes in Action book"],
            "estimated_hours": 6,
            "why": "Listed as a core requirement in the JD.",
        }
    ]
}


# ---------------------------------------------------------------------------
# Task 3.5.2 — Technical questions
# ---------------------------------------------------------------------------

def test_generate_technical_questions_returns_dict():
    with patch("agents.interview_prep.ClaudeClient") as MockClient, \
         patch("agents.interview_prep.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = FAKE_TECHNICAL
        result = generate_technical_questions(_make_job(), RESUME_DATA)

    assert "technical_questions" in result
    assert "Python" in result["technical_questions"]
    assert len(result["technical_questions"]["Python"]) == 3


def test_generate_technical_questions_passes_jd_to_prompt():
    captured = {}

    def fake_load_prompt(template_name, **kwargs):
        captured.update(kwargs)
        return "prompt"

    with patch("agents.interview_prep.ClaudeClient") as MockClient, \
         patch("agents.interview_prep.load_prompt", side_effect=fake_load_prompt):
        MockClient.return_value.chat_json.return_value = FAKE_TECHNICAL
        generate_technical_questions(_make_job(), RESUME_DATA)

    assert captured["company"] == "Stripe"
    assert "Python" in captured["job_description"]


# ---------------------------------------------------------------------------
# Task 3.5.3 — Behavioral questions
# ---------------------------------------------------------------------------

def test_generate_behavioral_questions_returns_list():
    with patch("agents.interview_prep.ClaudeClient") as MockClient, \
         patch("agents.interview_prep.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = FAKE_BEHAVIORAL
        result = generate_behavioral_questions(_make_job(), RESUME_DATA)

    assert "behavioral_questions" in result
    assert len(result["behavioral_questions"]) == 2
    assert result["behavioral_questions"][0]["trait"] == "ownership"


def test_generate_behavioral_questions_has_star_framework():
    with patch("agents.interview_prep.ClaudeClient") as MockClient, \
         patch("agents.interview_prep.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = FAKE_BEHAVIORAL
        result = generate_behavioral_questions(_make_job(), RESUME_DATA)

    for bq in result["behavioral_questions"]:
        assert "star_framework" in bq
        assert "question" in bq


# ---------------------------------------------------------------------------
# Task 3.5.4 — Company questions
# ---------------------------------------------------------------------------

def test_generate_company_questions_returns_both_sections():
    with patch("agents.interview_prep.ClaudeClient") as MockClient, \
         patch("agents.interview_prep.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = FAKE_COMPANY
        result = generate_company_questions(_make_job(), RESUME_DATA)

    assert "company_questions" in result
    assert "why_us_talking_points" in result
    assert len(result["company_questions"]) == 2
    assert len(result["why_us_talking_points"]) == 2


def test_generate_company_questions_has_talking_points():
    with patch("agents.interview_prep.ClaudeClient") as MockClient, \
         patch("agents.interview_prep.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = FAKE_COMPANY
        result = generate_company_questions(_make_job(), RESUME_DATA)

    for cq in result["company_questions"]:
        assert "question" in cq
        assert "talking_point" in cq


# ---------------------------------------------------------------------------
# Task 3.5.6 — Study plan
# ---------------------------------------------------------------------------

def test_generate_study_plan_returns_items():
    gap_analysis = {"hard_gaps": ["Kubernetes"], "soft_gaps": ["distributed systems"]}
    with patch("agents.interview_prep.ClaudeClient") as MockClient, \
         patch("agents.interview_prep.load_prompt", return_value="prompt"):
        MockClient.return_value.chat_json.return_value = FAKE_STUDY_PLAN
        result = generate_study_plan(_make_job(), RESUME_DATA, gap_analysis)

    assert "study_plan" in result
    assert result["study_plan"][0]["topic"] == "Kubernetes"
    assert result["study_plan"][0]["priority"] == "high"
    assert result["study_plan"][0]["estimated_hours"] == 6


def test_generate_study_plan_skips_claude_when_no_gaps():
    """If no gaps exist, Claude should not be called."""
    with patch("agents.interview_prep.ClaudeClient") as MockClient:
        result = generate_study_plan(_make_job(), RESUME_DATA, {"hard_gaps": [], "soft_gaps": []})
        MockClient.assert_not_called()

    assert result == {"study_plan": []}


def test_generate_study_plan_passes_gaps_to_prompt():
    captured = {}

    def fake_load_prompt(template_name, **kwargs):
        captured.update(kwargs)
        return "prompt"

    gap_analysis = {"hard_gaps": ["Rust"], "soft_gaps": ["concurrency"]}
    with patch("agents.interview_prep.ClaudeClient") as MockClient, \
         patch("agents.interview_prep.load_prompt", side_effect=fake_load_prompt):
        MockClient.return_value.chat_json.return_value = FAKE_STUDY_PLAN
        generate_study_plan(_make_job(), RESUME_DATA, gap_analysis)

    assert "Rust" in captured["hard_gaps"]
    assert "concurrency" in captured["soft_gaps"]


# ---------------------------------------------------------------------------
# Task 3.5.5 — Question pool builder
# ---------------------------------------------------------------------------

def _make_prep(technical=None, behavioral=None, company=None):
    prep = MagicMock(spec=InterviewPrep)
    prep.technical_questions = technical or {
        "Python": ["Q1?", "Q2?"],
        "Go": ["Q3?"],
    }
    prep.behavioral_questions = behavioral or [
        {"question": "Tell me about a time...", "trait": "ownership", "star_framework": "..."},
    ]
    prep.company_questions = company or {
        "questions": [{"question": "What's the team structure?", "talking_point": "..."}],
        "why_us": ["Reason 1"],
    }
    prep.mock_sessions = []
    return prep


def test_build_question_pool_includes_all_types():
    prep = _make_prep()
    pool = _build_question_pool(prep)
    types = {q["type"] for q in pool}
    assert "technical" in types
    assert "behavioral" in types
    assert "company" in types


def test_build_question_pool_not_empty():
    prep = _make_prep()
    pool = _build_question_pool(prep)
    assert len(pool) > 0


def test_build_question_pool_empty_prep():
    prep = MagicMock(spec=InterviewPrep)
    prep.technical_questions = {}
    prep.behavioral_questions = []
    prep.company_questions = {"questions": [], "why_us": []}
    pool = _build_question_pool(prep)
    assert pool == []


# ---------------------------------------------------------------------------
# _score_answer
# ---------------------------------------------------------------------------

def test_score_answer_returns_score_and_critique():
    fake_feedback = {
        "score": 7,
        "critique": "Good use of STAR structure but missing quantifiable result.",
        "suggested_answer": "A stronger answer would include specific metrics...",
    }
    client = MagicMock()
    client.chat_json.return_value = fake_feedback

    result = _score_answer(client, "Tell me about a time...", "I led a team...", "behavioral", _make_job())

    assert result["score"] == 7
    assert "critique" in result
    assert "suggested_answer" in result
