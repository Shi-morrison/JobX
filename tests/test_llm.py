"""Tests for tools/llm.py — run with: .venv/bin/pytest tests/test_llm.py -v"""
import json
import pytest
from unittest.mock import MagicMock, patch
from tools.llm import ClaudeClient, load_prompt


# ---------------------------------------------------------------------------
# load_prompt
# ---------------------------------------------------------------------------

def test_load_prompt_missing_file():
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        load_prompt("nonexistent")


def test_load_prompt_substitution(tmp_path, monkeypatch):
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "test.txt").write_text("Hello {name}, score is {score}.")
    monkeypatch.setattr("tools.llm._PROMPTS_DIR", prompt_dir)
    result = load_prompt("test", name="Alice", score="9")
    assert result == "Hello Alice, score is 9."


# ---------------------------------------------------------------------------
# ClaudeClient._parse_json
# ---------------------------------------------------------------------------

def test_parse_json_plain():
    result = ClaudeClient._parse_json('{"key": "value"}')
    assert result == {"key": "value"}


def test_parse_json_strips_markdown_fence():
    fenced = "```json\n{\"key\": \"value\"}\n```"
    assert ClaudeClient._parse_json(fenced) == {"key": "value"}


def test_parse_json_strips_plain_fence():
    fenced = "```\n{\"key\": 1}\n```"
    assert ClaudeClient._parse_json(fenced) == {"key": 1}


def test_parse_json_invalid_raises():
    with pytest.raises(ValueError, match="Could not parse"):
        ClaudeClient._parse_json("this is not json")


# ---------------------------------------------------------------------------
# ClaudeClient.chat (mocked — no real API call)
# ---------------------------------------------------------------------------

def _make_client_with_mock(response_text: str) -> ClaudeClient:
    """Return a ClaudeClient whose underlying API call returns response_text."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=response_text)]

    client = ClaudeClient()
    client._call = MagicMock(return_value=response_text)
    return client


def test_chat_returns_string():
    client = _make_client_with_mock("Hello!")
    result = client.chat([{"role": "user", "content": "Hi"}])
    assert result == "Hello!"


def test_chat_with_system_passes_system():
    client = ClaudeClient()
    client._call = MagicMock(return_value="response")
    client.chat_with_system("You are helpful.", [{"role": "user", "content": "Hi"}])
    call_kwargs = client._call.call_args
    assert call_kwargs.kwargs["system"] == "You are helpful."


def test_chat_json_parses_response():
    client = _make_client_with_mock('{"fit_score": 8, "reasoning": "good match"}')
    result = client.chat_json([{"role": "user", "content": "score this job"}])
    assert result["fit_score"] == 8
    assert result["reasoning"] == "good match"


def test_chat_json_retries_on_bad_json():
    """If first response is invalid JSON, client should retry once."""
    good_json = '{"fit_score": 7}'
    call_count = 0

    def fake_call(messages, system, max_tokens, _attempt=0):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "oops not json"
        return good_json

    client = ClaudeClient()
    client._call = fake_call
    result = client.chat_json([{"role": "user", "content": "score"}])
    assert result == {"fit_score": 7}
    assert call_count == 2
