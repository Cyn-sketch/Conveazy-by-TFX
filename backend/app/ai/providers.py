"""LLM provider abstraction. Providers only turn a prompt into JSON; validation,
safety and context assembly live in the engine so they apply to every provider."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from ..config import Settings, get_settings

log = logging.getLogger("conveazy.ai")


class ProviderError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _status(e: Exception) -> int | None:
    return e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None


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
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ProviderError(f"Model returned invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ProviderError("Model returned JSON that is not an object")
    return data


class OpenAIProvider:
    name = "openai"
    live = True

    def __init__(self, s: Settings):
        self.s = s

    def complete_json(self, req: LLMRequest) -> dict:
        try:
            r = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.s.openai_api_key}"},
                json={
                    "model": self.s.openai_model,
                    "temperature": 0.6,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": req.system},
                        {"role": "user", "content": req.user},
                    ],
                },
                timeout=self.s.ai_timeout_seconds,
            )
            r.raise_for_status()
            return _parse_json(r.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError) as e:
            raise ProviderError(f"OpenAI request failed: {type(e).__name__} {_status(e) or ''}".strip(), _status(e)) from e


_GEMINI = "https://generativelanguage.googleapis.com/v1beta"
_gemini_model_swap: dict[str, str] = {}  # configured name -> working name found after a 404


def _model_rank(name: str) -> tuple:
    """Prefer a stable "latest" Flash alias, then the newest stable Flash version."""
    n = name.lower()
    version = tuple(int(x) for x in re.findall(r"(\d+)", n.split("gemini-", 1)[-1])[:2])
    return ("latest" in n, not re.search(r"preview|exp", n), version)


def pick_gemini_model(models: list[dict]) -> str | None:
    names = [m.get("name", "").removeprefix("models/") for m in models
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    flash = [n for n in names if "flash" in n and not re.search(r"lite|image|tts|audio|live|thinking|embed", n)]
    return max(flash, key=_model_rank) if flash else None


class GeminiProvider:
    name = "gemini"
    live = True

    def __init__(self, s: Settings):
        self.s = s

    def _post(self, model: str, req: LLMRequest) -> httpx.Response:
        return httpx.post(
            f"{_GEMINI}/models/{model}:generateContent",
            headers={"x-goog-api-key": self.s.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": req.system}]},
                "contents": [{"role": "user", "parts": [{"text": req.user}]}],
                "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"},
            },
            timeout=self.s.ai_timeout_seconds,
        )

    def _discover(self) -> str | None:
        """Ask Google which models this key can use (called only after a 404)."""
        try:
            r = httpx.get(f"{_GEMINI}/models", params={"pageSize": 1000},
                          headers={"x-goog-api-key": self.s.gemini_api_key}, timeout=15)
            r.raise_for_status()
            return pick_gemini_model(r.json().get("models", []))
        except (httpx.HTTPError, ValueError) as e:
            log.warning("gemini model discovery failed: %s", type(e).__name__)
            return None

    def complete_json(self, req: LLMRequest) -> dict:
        configured = self.s.gemini_model
        model = _gemini_model_swap.get(configured, configured)
        try:
            r = self._post(model, req)
            if r.status_code == 404:
                found = self._discover()
                if found and found != model:
                    log.warning("gemini model %r not found; switching to %r", model, found)
                    _gemini_model_swap[configured] = model = found
                    r = self._post(model, req)
            r.raise_for_status()
            parts = r.json()["candidates"][0]["content"]["parts"]
            text = next(p["text"] for p in parts if "text" in p and not p.get("thought"))
            return _parse_json(text)
        except (httpx.HTTPError, KeyError, IndexError, StopIteration) as e:
            raise ProviderError(f"Gemini request failed ({model}): {type(e).__name__} {_status(e) or ''}".strip(),
                                _status(e)) from e


def get_provider(settings: Settings | None = None) -> LLMProvider:
    from .mock import MockProvider

    s = settings or get_settings()
    if s.ai_provider == "openai" and s.openai_api_key:
        return OpenAIProvider(s)
    if s.ai_provider == "gemini" and s.gemini_api_key:
        return GeminiProvider(s)
    # Falls back to mock when no key is configured. Responses are labelled live=false.
    return MockProvider()
