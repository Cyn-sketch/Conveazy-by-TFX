"""LLM provider abstraction. Providers only turn a prompt into JSON; validation,
safety and context assembly live in the engine so they apply to every provider."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from ..config import Settings, get_settings


class ProviderError(RuntimeError):
    pass


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
            raise ProviderError(f"OpenAI request failed: {type(e).__name__}") from e


class GeminiProvider:
    name = "gemini"
    live = True

    def __init__(self, s: Settings):
        self.s = s

    def complete_json(self, req: LLMRequest) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_model}:generateContent"
        try:
            r = httpx.post(
                url,
                headers={"x-goog-api-key": self.s.gemini_api_key},
                json={
                    "systemInstruction": {"parts": [{"text": req.system}]},
                    "contents": [{"role": "user", "parts": [{"text": req.user}]}],
                    "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"},
                },
                timeout=self.s.ai_timeout_seconds,
            )
            r.raise_for_status()
            return _parse_json(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except (httpx.HTTPError, KeyError, IndexError) as e:
            raise ProviderError(f"Gemini request failed: {type(e).__name__}") from e


def get_provider(settings: Settings | None = None) -> LLMProvider:
    from .mock import MockProvider

    s = settings or get_settings()
    if s.ai_provider == "openai" and s.openai_api_key:
        return OpenAIProvider(s)
    if s.ai_provider == "gemini" and s.gemini_api_key:
        return GeminiProvider(s)
    # Falls back to mock when no key is configured. Responses are labelled live=false.
    return MockProvider()
