from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.ai.mock import MockProvider
from app.ai.providers import ClaudeProvider, LLMRequest, ProviderError, get_provider
from app.config import Settings


class FakeMessages:
    def __init__(self, result):
        self.result, self.calls = result, []

    def create(self, **kw):
        self.calls.append(kw)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _provider(result):
    msgs = FakeMessages(result)
    p = ClaudeProvider(Settings(_env_file=None, anthropic_api_key="k"), client=SimpleNamespace(messages=msgs))
    return p, msgs


def _msg(*blocks, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=list(blocks))


REQ = LLMRequest("bridge", "system prompt", "user text")


def test_reads_json_from_text_blocks_and_skips_thinking():
    p, msgs = _provider(_msg(SimpleNamespace(type="thinking", thinking=""),
                             SimpleNamespace(type="text", text='Here you go:\n```json\n{"a": 1}\n```')))
    assert p.complete_json(REQ) == {"a": 1}
    call = msgs.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["system"].startswith("system prompt") and "JSON" in call["system"]
    assert call["messages"] == [{"role": "user", "content": "user text"}]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_refusal_and_cutoff_are_errors(stop):
    p, _ = _provider(_msg(SimpleNamespace(type="text", text="{}"), stop=stop))
    with pytest.raises(ProviderError) as e:
        p.complete_json(REQ)
    assert not e.value.busy


def test_overload_is_busy():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.InternalServerError("overloaded", response=httpx.Response(529, request=req), body=None)
    p, _ = _provider(err)
    with pytest.raises(ProviderError) as e:
        p.complete_json(REQ)
    assert e.value.busy


def test_key_picks_claude_even_with_old_provider_setting(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", " 'k' ")
    monkeypatch.setenv("CONVEAZY_AI_PROVIDER", "gemini")
    s = Settings(_env_file=None)
    assert s.ai_provider == "claude" and s.anthropic_api_key == "k"
    assert isinstance(get_provider(s), ClaudeProvider)


def test_no_key_or_forced_mock_uses_mock(monkeypatch):
    assert isinstance(get_provider(Settings(_env_file=None)), MockProvider)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("CONVEAZY_AI_PROVIDER", "mock")
    assert isinstance(get_provider(Settings(_env_file=None)), MockProvider)
