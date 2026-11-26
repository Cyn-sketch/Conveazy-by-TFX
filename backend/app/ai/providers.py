"""LLM provider abstraction. Providers only turn a prompt into JSON; validation,
safety and context assembly live in the engine so they apply to every provider."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Protocol

import anthropic

from ..config import Settings, get_settings

log = logging.getLogger("conveazy.ai")


BUSY_STATUSES = {429, 500, 502, 503, 504, 529}  # 529 = Anthropic "overloaded"


class ProviderError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, busy: bool = False):
        super().__init__(message)
        self.status = status
        self.busy = busy or status in BUSY_STATUSES


@dataclass
class LLMRequest:
    module: str  # translator | partner | myself
    system: str
    user: str
    payload: dict = field(default_factory=dict)  # structured inputs; the mock provider uses these


class LLMProvider(Protocol):
    name: str
    live: bool

    def complete_json(self, req: LLMRequest) -> dict: ...


def _parse_json(text: str) -> dict:
    text = text.strip()
    if not text.startswith("{"):
        # Tolerate code fences or a stray sentence around the object.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ProviderError(f"Model returned invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ProviderError("Model returned JSON that is not an object")
    return data


JSON_RULE = ("\n\nReply with a single JSON object only: no code fences, no text before or after it.")


class ClaudeProvider:
    name = "claude"
    live = True

    def __init__(self, s: Settings, client: anthropic.Anthropic | None = None):
        self.s = s
        # The SDK already retries rate limits and overload (429/5xx) with backoff; one retry keeps a
        # request well inside the app's time limit.
        self.client = client or anthropic.Anthropic(
            api_key=s.anthropic_api_key, timeout=s.ai_timeout_seconds, max_retries=1)

    def complete_json(self, req: LLMRequest) -> dict:
        try:
            msg = self.client.messages.create(
                model=self.s.claude_model,
                max_tokens=8000,
                output_config={"effort": self.s.claude_effort},
                system=req.system + JSON_RULE,
                messages=[{"role": "user", "content": req.user}],
            )
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Claude request failed: {type(e).__name__} {e.status_code}", e.status_code) from e
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
            raise ProviderError(f"Claude request failed: {type(e).__name__}", busy=True) from e
        if msg.stop_reason == "refusal":
            raise ProviderError("Claude declined this request")
        if msg.stop_reason == "max_tokens":
            raise ProviderError("Claude's answer was cut off")
        text = "".join(b.text for b in msg.content if b.type == "text")
        return _parse_json(text)


def get_provider(settings: Settings | None = None) -> LLMProvider:
    from .mock import MockProvider

    s = settings or get_settings()
    if s.ai_provider == "claude" and s.anthropic_api_key:
        return ClaudeProvider(s)
    # Falls back to mock when no key is configured. Responses are labelled live=false.
    return MockProvider()
