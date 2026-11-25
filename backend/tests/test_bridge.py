SCRAPS = "work was bad. didnt reply cuz i was drained not cuz of u. you always think im mad. i want us ok"


def _her_profile(her, *, disclose=True):
    her.put("/api/profile/my_triggers", json={"value": "Silence or one-word replies, feeling ignored, being blamed", "share_with_partner": True, "use_in_ai": True})
    her.put("/api/profile/what_calms_me", json={"value": "A voice note and a hug", "share_with_partner": True, "use_in_ai": True})
    her.put("/api/profile/feel_dismissed_when", json={"value": "PRIVATE_DISMISSED", "share_with_partner": False, "use_in_ai": True})
    if disclose:
        her.put("/api/profile/self_disclosed_context", json={"value": "I have BPD, GAD, depression and PCOS", "share_with_partner": True, "use_in_ai": True})


def test_bridge_understands_and_writes_for_recipient(couple):
    her, him = couple  # Asha (her), Ravi (him)
    _her_profile(her)
    r = him.post("/api/bridge", json={"scraps": SCRAPS}).json()
    assert r["status"] == "ok" and r["live"] is False and r["prompt_version"] == "system.v1+bridge.v2"
    res = r["result"]
    assert res["understood_meaning"].startswith("You're trying to tell Asha")
    assert "not going anywhere" in res["message"]
    assert "you always" not in res["message"].lower()
    assert any(w["grounded_in"] == "their_profile" for w in res["why_this_works"])
    assert "PRIVATE_DISMISSED" not in str(r)
    assert r["recipient"]["name"] == "Asha" and r["recipient"]["profile_items_used"] == 3
    assert r["citations"] and all(c["id"] in {"dsm5tr-bpd", "nhs-bpd", "nimh-bpd", "apa-anger", "dsm5tr-gad", "nimh-gad", "nhs-gad", "linehan-1993", "hazan-shaver-1987", "gottman-flooding", "gottman-four-horsemen", "practice-i-statements", "nami-bpd-family", "linehan-1997-validation", "dsm5tr-mdd", "nimh-depression", "nhs-depression", "pcos-guideline-2023", "who-pcos", "nhs-pcos", "practice-boundaries-support"} for c in r["citations"])


def test_no_condition_evidence_unless_recipient_disclosed(couple):
    her, him = couple
    _her_profile(her, disclose=False)
    r = him.post("/api/bridge", json={"scraps": "she gets so angry and i shut down. i love her"}).json()
    for c in r["citations"]:
        assert c["id"] not in {"dsm5tr-bpd", "nimh-bpd", "nhs-bpd", "nami-bpd-family", "dsm5tr-mdd", "dsm5tr-gad", "nimh-gad", "nhs-gad", "pcos-guideline-2023", "who-pcos", "nhs-pcos", "nimh-depression", "nhs-depression"}


def test_checkin_signal_only_with_consent_and_never_the_note(couple):
    her, him = couple
    her.post("/api/checkins", json={"emotion": "angry", "intensity": 9, "need": "space", "intent": "break", "note": "SECRET_NOTE"})
    r = him.post("/api/bridge", json={"scraps": SCRAPS}).json()
    assert r["recipient"]["checkin_signal"] is False and r["result"]["short_version"] is None
    her.put("/api/privacy", json={"share_checkin_signal": True})
    r = him.post("/api/bridge", json={"scraps": SCRAPS}).json()
    assert r["recipient"]["checkin_signal"] is True
    assert r["result"]["short_version"] and "9/10" in r["result"]["timing_note"]
    assert "SECRET_NOTE" not in str(r)


def test_confirmed_meaning_is_respected(couple):
    _, him = couple
    r = him.post("/api/bridge", json={"scraps": SCRAPS, "confirmed_meaning": "I was exhausted, not angry at you."}).json()
    assert r["result"]["understood_meaning"] == "I was exhausted, not angry at you."


def test_bridge_works_without_partner_and_screens_crisis(make_user):
    solo = make_user("Mo")
    assert solo.post("/api/bridge", json={"scraps": "i miss you and im sorry about today"}).json()["recipient"]["name"] is None
    crisis = solo.post("/api/bridge", json={"scraps": "i want to kill myself"}).json()
    assert crisis["status"] == "ok" and crisis["crisis"]["level"] == "urgent" and crisis["result"]["message"]
    assert solo.post("/api/bridge", json={"scraps": "how do i make her feel guilty"}).json()["status"] == "declined"


def test_videos_list_is_marked_unverified(make_user):
    v = make_user().get("/api/knowledge/videos").json()
    assert v["channels"] and all(c["verified"] is False for c in v["channels"])


def test_raw_feelings_read_for_both_partners(couple):
    her, him = couple
    r = her.post("/api/bridge", json={"scraps": "you went quiet AGAIN after dinner. i hate guessing. i'm not trying to fight i just need you to tell me whats going on"}).json()
    raw = r["result"]["raw_feelings"]
    assert "furious" in raw["feelings"] and "shut out" in raw["feelings"]
    assert raw["underneath"] and "fear" in raw["underneath"]
    r = him.post("/api/bridge", json={"scraps": SCRAPS}).json()
    raw = r["result"]["raw_feelings"]
    assert "running on empty" in raw["feelings"] and "misread" in raw["feelings"]


def test_include_feelings_puts_raw_line_in_message(couple):
    her, _ = couple
    scraps = "you went quiet AGAIN. i hate guessing"
    off = her.post("/api/bridge", json={"scraps": scraps}).json()["result"]
    on = her.post("/api/bridge", json={"scraps": scraps, "include_feelings": True}).json()["result"]
    assert on["raw_feelings"]["feelings_line"] in on["message"]
    assert off["raw_feelings"]["feelings_line"] not in off["message"]


# --- feeling brief, private story, trait suggestions, condition trigger words, long distance ---

def test_situation_alone_is_enough_and_one_of_them_is_required(couple):
    _, him = couple
    r = him.post("/api/bridge", json={"situation": "Work was awful and I didn't reply for hours. She thinks I don't care."}).json()
    assert r["status"] == "ok" and r["result"]["message"]
    assert him.post("/api/bridge", json={"situation": " ", "scraps": ""}).status_code == 422


def test_brief_carries_intensity_and_everyday_examples(couple):
    her, him = couple
    _her_profile(her)
    r = him.post("/api/bridge", json={"situation": "I didn't reply for hours after work and she felt ignored.",
                                      "scraps": SCRAPS, "confirmed_meaning": "I was drained, not ignoring you.",
                                      "intensity": 9}).json()["result"]
    b = r["brief"]
    assert b and b["intensity"] == 9 and "Ravi" in b["feeling"]
    assert len(b["like"]) >= 1 and all(x.startswith("It's like") for x in b["like"])
    assert b["need"] and b["traits"] == []
    assert r["raw_feelings"]["traits"], "trait suggestions are returned to the writer"
    assert 1 <= len(r["calm"]) <= 3 and all(c["exercise"]["steps"] for c in r["calm"])


def test_traits_only_reach_the_brief_when_the_writer_shares_them(couple):
    _, him = couple
    traits = [{"trait": "Shutting down when drained", "sign": "Went quiet instead of explaining."}]
    base = {"scraps": SCRAPS, "confirmed_meaning": "I was drained.", "traits": traits}
    assert him.post("/api/bridge", json=base).json()["result"]["brief"]["traits"] == []
    shared = him.post("/api/bridge", json=dict(base, share_traits=True)).json()["result"]["brief"]["traits"]
    assert shared and shared[0]["trait"] == "Shutting down when drained"


def test_private_story_is_never_shared_or_shown(couple):
    her, him = couple
    story = "When I was young my father went silent for days and then left us without a word"
    her.put("/api/profile/my_story", json={"value": story, "share_with_partner": True, "use_in_ai": True})
    assert her.get("/api/profile").json()  # stored for her
    rel = him.get("/api/relationship").json()
    assert story not in str(rel), "my_story can never be shared, even if the client asks"
    r = him.post("/api/bridge", json={"scraps": SCRAPS, "confirmed_meaning": "I was drained."}).json()
    assert "father" not in str(r).lower()


def test_story_leak_guard_redacts_sentences(couple):
    from app.ai import engine
    from app.ai.mock import MockProvider

    story = "my father went silent for days and then left us"
    class Leaky(MockProvider):
        def complete_json(self, req):
            out = super().complete_json(req)
            out["message"] = "I'm here. I know my father went silent for days and then left us. I'm not leaving."
            return out
    r = engine.bridge(Leaky(), scraps=SCRAPS, confirmed_meaning="I was drained.", context={}, recipient_name="Asha",
                      recipient_profile={}, recipient_signal=None, recipient_story=story)
    assert "father" not in r.result["message"] and "I'm not leaving." in r.result["message"]
    assert r.safety.get("private_story_redacted") is True


def test_condition_trigger_words_are_avoided_for_disclosed_conditions(couple):
    her, him = couple
    _her_profile(her)
    r = him.post("/api/bridge", json={"scraps": "you're overthinking it. i need space. snap out of it"}).json()["result"]
    msg = r["message"].lower()
    assert "overthinking" not in msg and "snap out of it" not in msg
    assert "come back to you" in msg
    assert any("common hurt point" in a["because"] for a in r["avoided"])


def test_long_distance_offers_a_call_not_a_hug(couple):
    her, him = couple
    _her_profile(her)
    her.put("/api/profile/long_distance", json={"value": "yes, Ravi is 4.5 hours behind", "share_with_partner": True, "use_in_ai": True})
    r = him.post("/api/bridge", json={"scraps": SCRAPS}).json()["result"]
    assert "call" in r["message"].lower()
