import json
import time
import re
from pathlib import Path
from typing import Any

import anthropic

from config import settings

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def load_prompt(template_name: str, **kwargs: Any) -> str:
    """Load a prompt template from tools/prompts/<template_name>.txt and fill in variables.

    Example:
        load_prompt("score_fit", job_title="Engineer", resume="...")
    """
    path = _PROMPTS_DIR / f"{template_name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    template = path.read_text(encoding="utf-8")
    return template.format(**kwargs)


class ClaudeClient:
    """Thin wrapper around the Anthropic SDK.

    All agents use this class instead of calling the SDK directly so that
    retry logic, model selection, and error handling live in one place.
    """

    def __init__(self, model: str | None = None):
        self.model = model or settings.claude_model

    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a message and return the response as a plain string.

        Args:
            messages: List of {"role": "user"/"assistant", "content": "..."} dicts.
            system: Optional system prompt string.
            max_tokens: Max tokens in the response.

        Returns:
            The assistant's reply as a string.
        """
        return self._call(messages=messages, system=system, max_tokens=max_tokens)

    def chat_with_system(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> str:
        """Convenience wrapper that puts the system prompt first.

        Use this when the system prompt is the main context — e.g. for agents
        that always start with a large persona/instruction block.
        """
        return self._call(messages=messages, system=system, max_tokens=max_tokens)

    def chat_json(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> dict:
        """Send a message and parse the response as JSON.

        Appends an instruction to the system prompt (or user message) asking
        Claude to reply with only valid JSON. Retries once if parsing fails.

        Returns:
            Parsed dict from Claude's JSON response.

        Raises:
            ValueError: If Claude's response cannot be parsed as JSON after retries.
        """
        json_instruction = (
            "You must respond with valid JSON only. "
            "Do not include any explanation, markdown formatting, or code blocks. "
            "Output raw JSON that can be parsed directly."
        )

        effective_system = f"{system}\n\n{json_instruction}" if system else json_instruction

        raw = self._call(messages=messages, system=effective_system, max_tokens=max_tokens)

        try:
            return self._parse_json(raw)
        except ValueError:
            # One retry with a stricter nudge appended to the conversation
            retry_messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "Your response was not valid JSON. Reply with only the JSON object, nothing else."},
            ]
            raw = self._call(messages=retry_messages, system=effective_system, max_tokens=max_tokens)
            return self._parse_json(raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call(
        self,
        messages: list[dict],
        system: str | None,
        max_tokens: int,
        _attempt: int = 0,
    ) -> str:
        """Make the API call with exponential backoff on rate limit / server errors."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        try:
            response = _client.messages.create(**kwargs)
            return response.content[0].text

        except anthropic.RateLimitError:
            return self._retry(_attempt, messages, system, max_tokens, reason="rate limit")

        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                return self._retry(_attempt, messages, system, max_tokens, reason=f"server error {e.status_code}")
            raise

    def _retry(
        self,
        attempt: int,
        messages: list[dict],
        system: str | None,
        max_tokens: int,
        reason: str,
    ) -> str:
        max_retries = 3
        if attempt >= max_retries:
            raise RuntimeError(f"Claude API failed after {max_retries} retries ({reason})")
        wait = 2 ** attempt  # 1s, 2s, 4s
        time.sleep(wait)
        return self._call(messages, system, max_tokens, _attempt=attempt + 1)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON from a string, stripping markdown fences if present."""
        text = text.strip()
        # Strip ```json ... ``` or ``` ... ``` fences if Claude added them anyway
        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
        if fenced:
            text = fenced.group(1)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse Claude response as JSON: {e}\n\nRaw response:\n{text}")
