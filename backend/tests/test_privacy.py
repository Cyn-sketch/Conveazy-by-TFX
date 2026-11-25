from sqlalchemy import select, text

from app.ai.context import build_personal_context
from app.db import get_engine
from app.models import User


def test_profile_sharing_is_opt_in(couple):
    a, b = couple
    a.put("/api/profile/feel_dismissed_when", json={"value": "My messages get one-word replies", "share_with_partner": False})
    a.put("/api/profile/reassurance_looks_like", json={"value": "A quick text when you'll be late", "share_with_partner": True})
    rel = b.get("/api/relationship").json()
    assert rel["status"] == "linked" and rel["partner"]["name"] == "Asha"
    values = [f["value"] for f in rel["partner_shared"]]
    assert values == ["A quick text when you'll be late"]


def test_partner_cannot_read_private_records(couple):
    a, b = couple
    ci = a.post("/api/checkins", json={"emotion": "hurt", "intensity": 6, "need": "reassurance", "intent": "reflect",
                                       "note": "private note"}).json()["checkin"]["id"]
    conv = a.post("/api/partner/ask", json={"question": "Why does silence feel like rejection?"}).json()["conversation_id"]
    assert b.get(f"/api/conversations/{conv}").status_code == 404
    assert b.delete(f"/api/conversations/{conv}").status_code == 404
    assert b.delete(f"/api/checkins/{ci}").status_code == 404
    assert b.get("/api/checkins").json()["checkins"] == []
    assert b.get("/api/conversations").json()["conversations"] == []
    # And the owner still has them.
    assert a.get(f"/api/conversations/{conv}").status_code == 200
    # Partner can't continue the conversation either.
    assert b.post("/api/partner/ask", json={"question": "hi there", "conversation_id": conv}).status_code == 404


def test_ai_context_only_uses_consented_partner_fields(app, couple):
    a, b = couple
    b.put("/api/profile/overwhelmed_helps", json={"value": "SHARED_AND_AI", "share_with_partner": True, "use_in_ai": True})
    b.put("/api/profile/boundaries", json={"value": "SHARED_NOT_AI", "share_with_partner": True, "use_in_ai": False})
    b.put("/api/profile/receive_affection", json={"value": "AI_NOT_SHARED", "share_with_partner": False, "use_in_ai": True})
    b.post("/api/checkins", json={"emotion": "angry", "intensity": 9, "need": "space", "intent": "break", "note": "PARTNER_CHECKIN"})
    a.put("/api/profile/communication_style", json={"value": "OWN_AI", "use_in_ai": True})
    a.put("/api/profile/boundaries", json={"value": "OWN_NOT_AI", "use_in_ai": False})
    from app.db import _SessionLocal
    with _SessionLocal() as db:
        asha = db.scalar(select(User).where(User.display_name == "Asha"))
        blob = str(build_personal_context(db, asha))
    assert "SHARED_AND_AI" in blob and "OWN_AI" in blob
    for leaked in ("SHARED_NOT_AI", "AI_NOT_SHARED", "PARTNER_CHECKIN", "OWN_NOT_AI", "angry"):
        assert leaked not in blob, leaked


def test_leaving_ends_access_immediately(couple):
    a, b = couple
    a.put("/api/profile/boundaries", json={"value": "No yelling", "share_with_partner": True})
    assert b.get("/api/relationship").json()["partner_shared"]
    assert b.delete("/api/relationship").status_code == 204
    assert b.get("/api/relationship").json()["status"] == "none"
    assert a.get("/api/relationship").json()["status"] == "none"


def test_invite_code_single_use_and_not_self(make_user):
    a, b, c = make_user("Asha"), make_user("Ravi"), make_user("Mo")
    code = a.post("/api/relationship/invite").json()["invite_code"]
    assert a.post("/api/relationship/join", json={"code": code}).status_code == 409
    assert b.post("/api/relationship/join", json={"code": code}).status_code == 200
    assert c.post("/api/relationship/join", json={"code": code}).status_code == 404


def test_sensitive_text_encrypted_at_rest(couple):
    a, _ = couple
    a.put("/api/profile/boundaries", json={"value": "PLAINTEXT_SECRET_123"})
    a.post("/api/checkins", json={"emotion": "hurt", "intensity": 5, "need": "clarity", "intent": "reflect", "note": "NOTE_SECRET_456"})
    a.post("/api/translate", json={"draft": "DRAFT_SECRET_789 you never listen", "save": True})
    with get_engine().connect() as conn:
        dump = " ".join(str(r) for t in ("profile_entries", "checkins", "messages")
                        for r in conn.execute(text(f"select * from {t}")))
    for secret in ("PLAINTEXT_SECRET_123", "NOTE_SECRET_456", "DRAFT_SECRET_789"):
        assert secret not in dump


def test_export_contains_only_own_data(couple):
    a, b = couple
    a.put("/api/profile/boundaries", json={"value": "ASHA_DATA", "share_with_partner": True})
    b.put("/api/profile/boundaries", json={"value": "RAVI_DATA", "share_with_partner": True})
    r = a.get("/api/privacy/export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "ASHA_DATA" in r.text and "RAVI_DATA" not in r.text


def test_account_deletion_removes_everything(couple):
    a, b = couple
    a.put("/api/profile/boundaries", json={"value": "x", "share_with_partner": True})
    a.post("/api/checkins", json={"emotion": "calm", "intensity": 2, "need": "listening", "intent": "reflect"})
    a.post("/api/partner/ask", json={"question": "How do I set boundaries kindly?"})
    assert a.request("DELETE", "/api/account", json={"password": "wrong-password!", "confirm": "DELETE"}).status_code == 403
    assert a.request("DELETE", "/api/account", json={"password": "correct-horse-battery", "confirm": "DELETE"}).status_code == 204
    assert a.get("/api/auth/me").status_code == 401
    assert b.get("/api/relationship").json()["status"] == "none"
    with get_engine().connect() as conn:
        for t in ("profile_entries", "checkins", "conversations", "messages", "consents"):
            rows = conn.execute(text(f"select count(*) from {t}")).scalar()
            if t == "consents":
                assert rows == 4  # Ravi's age confirmation + onboarding consents only
            else:
                assert rows == 0, t


def test_consent_ledger_and_training_default_off(make_user):
    a = make_user("Asha")
    p = a.get("/api/privacy").json()
    assert p["consents"]["model_training"] is False
    assert p["partner_can_see"]["checkins"] is False
    a.put("/api/privacy", json={"ai_processing": False})
    p = a.get("/api/privacy").json()
    assert p["consents"]["ai_processing"] is False
    assert len(p["consent_history"]) == 5


def test_save_history_off_stores_nothing(make_user):
    a = make_user("Asha")
    a.put("/api/privacy", json={"save_history": False})
    r = a.post("/api/partner/ask", json={"question": "Why does my partner withdraw?"}).json()
    assert "conversation_id" not in r
    assert a.get("/api/conversations").json()["conversations"] == []


def test_retention_purge(app, make_user):
    from datetime import UTC, datetime, timedelta

    from app.db import _SessionLocal
    from app.models import CheckIn
    from app.services import purge_expired
    a = make_user("Asha")
    a.put("/api/privacy", json={"retention_days": 30})
    a.post("/api/checkins", json={"emotion": "calm", "intensity": 2, "need": "listening", "intent": "reflect"})
    with _SessionLocal() as db:
        ci = db.scalar(select(CheckIn))
        ci.created_at = datetime.now(UTC) - timedelta(days=31)
        db.commit()
        assert purge_expired(db, db.scalar(select(User))) == 1
