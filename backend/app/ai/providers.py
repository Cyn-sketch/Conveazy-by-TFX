"""LLM provider abstraction. Providers only turn a prompt into JSON; validation,
safety and context assembly live in the engine so they apply to every provider."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from ..config import Settings, get_settings

log = logging.getLogger("conveazy.ai")


BUSY_STATUSES = {429, 500, 502, 503, 504}


class ProviderError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, busy: bool = False):
        super().__init__(message)
        self.status = status
        self.busy = busy or status in BUSY_STATUSES


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
_gemini_available: list[str] | None = None  # models this key can use, best first (fetched once, on demand)
_gemini_preferred: tuple[str, float] | None = None  # a backup that worked while the main model was busy, until

_SKIP = r"image|tts|audio|live|thinking|embed|aqa|learnlm|gemma"


def _model_rank(name: str) -> tuple:
    """Prefer a stable "latest" Flash alias, then the newest stable Flash version."""
    n = name.lower()
    version = tuple(int(x) for x in re.findall(r"(\d+)", n.split("gemini-", 1)[-1])[:2])
    return ("latest" in n, not re.search(r"preview|exp", n), version)


def _usable(models: list[dict]) -> list[str]:
    return [m.get("name", "").removeprefix("models/") for m in models
            if "generateContent" in m.get("supportedGenerationMethods", [])]


def pick_gemini_model(models: list[dict]) -> str | None:
    flash = [n for n in _usable(models) if "flash" in n and "lite" not in n and not re.search(_SKIP, n)]
    return max(flash, key=_model_rank) if flash else None


def rank_gemini_backups(models: list[dict]) -> list[str]:
    """Every Flash model (full first, then lite), best first: candidates when the main model is busy."""
    flash = [n for n in _usable(models) if "flash" in n and not re.search(_SKIP, n)]
    return sorted(flash, key=lambda n: ("lite" not in n, _model_rank(n)), reverse=True)


class GeminiProvider:
    name = "gemini"
    live = True
    max_models = 2  # main model + one backup, so a request stays around a minute at most

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

    def _available(self) -> list[dict]:
        """Ask Google which models this key can use (only after a 404 or a busy model)."""
        try:
            r = httpx.get(f"{_GEMINI}/models", params={"pageSize": 1000},
                          headers={"x-goog-api-key": self.s.gemini_api_key}, timeout=10)
            r.raise_for_status()
            return r.json().get("models", [])
        except (httpx.HTTPError, ValueError) as e:
            log.warning("gemini model discovery failed: %s", type(e).__name__)
            return []

    def _discover(self) -> str | None:
        return pick_gemini_model(self._available())

    def _backups(self, tried: set[str]) -> list[str]:
        global _gemini_available
        configured = [m.strip() for m in self.s.gemini_fallback_models.split(",") if m.strip()]
        if _gemini_available is None:
            _gemini_available = rank_gemini_backups(self._available())
        return [m for m in dict.fromkeys(configured + _gemini_available) if m not in tried]

    def _once(self, model: str, req: LLMRequest) -> tuple[str, dict]:
        r = self._post(model, req)
        if r.status_code == 404:
            found = self._discover()
            if found and found != model:
                log.warning("gemini model %r not found; switching to %r", model, found)
                _gemini_model_swap[self.s.gemini_model] = model = found
                r = self._post(model, req)
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        text = next(p["text"] for p in parts if "text" in p and not p.get("thought"))
        return model, _parse_json(text)

    def complete_json(self, req: LLMRequest) -> dict:
        global _gemini_preferred
        main = _gemini_model_swap.get(self.s.gemini_model, self.s.gemini_model)
        model = _gemini_preferred[0] if _gemini_preferred and _gemini_preferred[1] > time.monotonic() else main
        tried: set[str] = set()
        while True:
            tried.add(model)
            try:
                used, data = self._once(model, req)
                if used != main:
                    _gemini_preferred = (used, time.monotonic() + 600)  # stay on the backup for 10 minutes
                elif _gemini_preferred:
                    _gemini_preferred = None
                return data
            except (httpx.HTTPError, KeyError, IndexError, StopIteration) as e:
                status = _status(e)
                busy = status in BUSY_STATUSES or isinstance(e, httpx.TimeoutException)
                err = ProviderError(f"Gemini request failed ({model}): {type(e).__name__} {status or ''}".strip(),
                                    status, busy)
                if not busy or len(tried) >= self.max_models:
                    raise err from e
                nxt = self._backups(tried)
                if not nxt:
                    raise err from e
                log.warning("gemini %s busy (%s); trying backup %s", model, status or type(e).__name__, nxt[0])
                model = nxt[0]


def get_provider(settings: Settings | None = None) -> LLMProvider:
    from .mock import MockProvider

    s = settings or get_settings()
    if s.ai_provider == "openai" and s.openai_api_key:
        return OpenAIProvider(s)
    if s.ai_provider == "gemini" and s.gemini_api_key:
        return GeminiProvider(s)
    # Falls back to mock when no key is configured. Responses are labelled live=false.
    return MockProvider()
