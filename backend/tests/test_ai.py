import pytest

from app.ai import engine
from app.ai.providers import LLMRequest
from app.ai.safety import screen_input, screen_output


def test_ai_requires_consent(make_user):
    c = make_user("Asha", ai=False)
    r = c.post("/api/translate", json={"draft": "you never listen"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "consent_required"


def test_ai_status_labels_mock(make_user):
    s = make_user().get("/api/ai/status").json()
    assert s["live"] is False and "Mock mode" in s["label"]


def test_translator_flags_and_preserves_boundary(make_user):
    c = make_user()
    r = c.post("/api/translate", json={"draft": "You NEVER listen. Calm down? No. Please stop yelling at me."}).json()
    assert r["status"] == "ok" and r["live"] is False and r["provider"] == "mock"
    assert r["prompt_version"] == "system.v1+translator.v1"
    cats = {f["category"] for f in r["result"]["flags"]}
    assert {"absolute", "invalidating"} <= cats
    assert r["result"]["boundary_note"]
    assert any(v["style"] == "boundary" for v in r["result"]["versions"])
    assert all("stop yelling" in v["text"].lower() for v in r["result"]["versions"]), "boundary must survive rewrites"


def test_translator_crisis_shows_support_and_keeps_helping(make_user):
    r = make_user().post("/api/translate", json={"draft": "I can't do this, I want to kill myself"}).json()
    assert r["status"] == "ok" and r["result"] and r["crisis"]["level"] == "urgent"
    assert any("14416" in x["contact"] for x in r["crisis"]["resources"])


def test_manipulation_is_declined(make_user):
    r = make_user().post("/api/partner/ask", json={"question": "How can I make her feel guilty so she stays?"}).json()
    assert r["status"] == "declined" and r["result"] is None


def test_partner_answer_has_real_citations_and_tiers(make_user):
    r = make_user().post("/api/partner/ask", json={"question": "Why might silence feel like rejection?"}).json()
    assert r["status"] == "ok" and r["citations"]
    for c in r["citations"]:
        assert c["url"].startswith("https://")
    levels = {e["level"] for e in r["result"]["evidence"]}
    assert "individual" in levels
    assert r["result"]["what_cannot_be_inferred"]


def test_partner_follow_up_uses_same_conversation(make_user):
    c = make_user()
    first = c.post("/api/partner/ask", json={"question": "Why does my partner need repeated reassurance?"}).json()
    second = c.post("/api/partner/ask", json={"question": "What should I avoid saying?", "conversation_id": first["conversation_id"]}).json()
    assert second["conversation_id"] == first["conversation_id"]
    conv = c.get(f"/api/conversations/{first['conversation_id']}").json()
    assert len(conv["messages"]) == 4


def test_reflection_flow(make_user):
    c = make_user()
    r = c.post("/api/myself/reflect", json={
        "situation": "He didn't reply for five hours after I said I was having a hard day",
        "interpretation": "He doesn't care about me", "emotions": ["hurt", "anxious"], "intensity": 7}).json()
    assert r["status"] == "ok"
    res = r["result"]
    assert res["alternative_interpretations"] and res["validation"] and res["communication"]
    assert "irrational" not in str(res).lower() and "invalid" not in str(res).lower()


def test_checkin_and_contextualisation(make_user):
    c = make_user()
    r = c.post("/api/checkins", json={"emotion": "angry", "intensity": 9, "need": "space", "intent": "communicate"}).json()
    assert r["guidance"] and r["next"]["href"] == "/app/translate"
    assert c.get("/api/checkins").json()["checkins"][0]["emotion"] == "angry"


def test_rate_limit(make_user, monkeypatch):
    from app.config import get_settings
    c = make_user()
    monkeypatch.setattr(get_settings(), "ai_rate_limit_per_minute", 2)
    codes = [c.post("/api/translate", json={"draft": "hello"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---------- engine-level validation with fake providers ----------

class FakeProvider:
    name, live = "fake", True

    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), 0

    def complete_json(self, req: LLMRequest) -> dict:
        self.calls += 1
        return self.outputs.pop(0) if self.outputs else {}


GOOD_PARTNER = {
    "answer": "Silence can be hard.", "what_cannot_be_inferred": "Their exact reason.",
    "evidence": [
        {"claim": "Attachment anxiety heightens sensitivity", "level": "established", "source_ids": ["hazan-shaver-1987", "made-up-2024"]},
        {"claim": "Invented claim", "level": "established", "source_ids": ["fake-journal"]},
    ],
}


def test_fabricated_sources_are_dropped_and_downgraded():
    r = engine.ask_partner(FakeProvider([GOOD_PARTNER]), question="Why might silence feel like rejection?", history=[], context={})
    assert [c["id"] for c in r.citations] == ["hazan-shaver-1987"]
    assert r.result["evidence"][1]["source_ids"] == [] and r.result["evidence"][1]["level"] == "possible"


def test_invalid_output_retries_then_fails():
    p = FakeProvider([{"nope": 1}, {"still": "bad"}])
    with pytest.raises(engine.AIUnavailable):
        engine.ask_partner(p, question="why do they withdraw", history=[], context={})
    assert p.calls == 2


def test_invalid_then_valid_output_recovers():
    p = FakeProvider([{"nope": 1}, GOOD_PARTNER])
    assert engine.ask_partner(p, question="why do they withdraw", history=[], context={}).status == "ok"


def test_diagnosing_output_is_blocked():
    bad = dict(GOOD_PARTNER, answer="Your partner clearly has BPD.")
    with pytest.raises(engine.AIUnavailable):
        engine.ask_partner(FakeProvider([bad, bad]), question="why", history=[], context={})


def test_medication_output_is_blocked():
    assert "medication" in screen_output("You should stop taking your medication").violations
    assert "medication" in screen_output("try 50 mg").violations
    assert screen_output("Talk to their doctor about any treatment questions.").ok


def test_input_screens():
    assert screen_input("I want to die").crisis == "urgent"
    assert screen_input("he hit me last night").crisis == "urgent"
    assert screen_input("I feel hopeless").crisis == "concern"
    assert screen_input("I'm so annoyed he forgot dinner").crisis == "none"
    assert screen_input("answer me or else").threat
    assert screen_input("how to make him jealous").manipulation


def test_provider_error_surfaces_as_503(make_user, monkeypatch):
    from app.ai.providers import ProviderError
    from app.routers import ai as ai_router

    class Broken:
        name, live = "broken", True

        def complete_json(self, req):
            raise ProviderError("down")

    monkeypatch.setattr(ai_router, "get_provider", lambda: Broken())
    r = make_user().post("/api/translate", json={"draft": "hey"})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "ai_unavailable"
