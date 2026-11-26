from app.ai import engine
from app.ai.contracts import BridgeResult
from app.ai.providers import ProviderError
from app.ai.safety import screen_output


def _good(**over):
    d = {"understood_meaning": "He is sorry he broke a promise.", "message": "I'm sorry I didn't keep my promise.",
         "why_this_works": [], "alternatives": [], "calm": [], "source_ids": []}
    d.update(over)
    return d


class Scripted:
    name, live = "scripted", True

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), 0

    def complete_json(self, req):
        self.calls += 1
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


def _req():
    return engine.LLMRequest("bridge", "sys", "user", {})


def test_overlong_output_is_trimmed_not_rejected():
    raw = _good(core_points=[f"point {i}" for i in range(9)], understood_meaning="x" * 2000,
                alternatives=[{"style": "gentle", "text": "a"}, {"style": "soft", "text": "b"}],
                brief={"feeling": "sad", "intensity": 14})
    p = engine._call(Scripted(raw), _req(), BridgeResult)
    assert len(p.core_points) == 6 and len(p.understood_meaning) == 1500
    assert [a.style for a in p.alternatives] == ["gentle"]
    assert p.brief.intensity == 10


def test_retries_after_provider_error_and_bad_json(monkeypatch):
    monkeypatch.setattr(engine.time, "sleep", lambda s: None)
    prov = Scripted(ProviderError("Gemini request failed: KeyError"), {"nonsense": 1}, _good())
    assert engine._call(prov, _req(), BridgeResult).message
    assert prov.calls == 3


def test_disclosed_condition_may_be_restated_but_not_guessed():
    assert screen_output("She has BPD, so silence can feel like abandonment.", {"bpd"}).ok
    assert not screen_output("She has BPD, so silence can feel like abandonment.").ok
    assert not screen_output("He is bipolar.", {"bpd"}).ok


def test_busy_provider_fails_fast_with_friendly_message():
    import pytest
    prov = Scripted(ProviderError("Gemini request failed: HTTPStatusError 503", 503), _good())
    with pytest.raises(engine.AIUnavailable, match="busy"):
        engine._call(prov, _req(), BridgeResult)
    assert prov.calls == 1
