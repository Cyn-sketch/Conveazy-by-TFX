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
    assert r["status"] == "ok" and r["live"] is False and r["prompt_version"] == "system.v1+bridge.v1"
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
    assert solo.post("/api/bridge", json={"scraps": "i want to kill myself"}).json()["status"] == "crisis"
    assert solo.post("/api/bridge", json={"scraps": "how do i make her feel guilty"}).json()["status"] == "declined"


def test_videos_list_is_marked_unverified(make_user):
    v = make_user().get("/api/knowledge/videos").json()
    assert v["channels"] and all(c["verified"] is False for c in v["channels"])
