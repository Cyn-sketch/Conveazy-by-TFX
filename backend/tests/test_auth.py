from fastapi.testclient import TestClient


def test_signup_login_me_logout(app, make_user):
    c = make_user("Asha", onboard=False)
    me = c.get("/api/auth/me").json()
    assert me["display_name"] == "Asha" and me["onboarded"] is False
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401
    r = c.post("/api/auth/login", json={"email": "asha@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 200
    assert c.get("/api/auth/me").status_code == 200


def test_session_cookie_is_httponly_and_lax(app):
    c = TestClient(app, headers={"X-Conveazy-Client": "web"})
    r = c.post("/api/auth/signup", json={"email": "x@example.com", "password": "correct-horse-battery", "display_name": "X", "confirm_adult": True})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_wrong_password_and_duplicate_email(app, make_user):
    c = make_user("Asha")
    r = c.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope-nope-nope"})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "bad_credentials"
    r = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "nope-nope-nope"})
    assert r.status_code == 401
    r = c.post("/api/auth/signup", json={"email": "ASHA@example.com", "password": "correct-horse-battery", "display_name": "A", "confirm_adult": True})
    assert r.status_code == 409


def test_short_password_rejected(app):
    c = TestClient(app, headers={"X-Conveazy-Client": "web"})
    r = c.post("/api/auth/signup", json={"email": "y@example.com", "password": "short", "display_name": "Y", "confirm_adult": True})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_input"


def test_csrf_header_required_for_writes(app, make_user):
    c = make_user("Asha")
    c.headers.pop("X-Conveazy-Client")
    assert c.get("/api/auth/me").status_code == 200
    r = c.post("/api/checkins", json={"emotion": "calm", "intensity": 2, "need": "listening", "intent": "reflect"})
    assert r.status_code == 403


def test_logout_everywhere_revokes_old_tokens(app, make_user):
    c = make_user("Asha")
    stolen = c.cookies.get("cz_session")
    assert c.post("/api/auth/logout?everywhere=true").status_code == 204
    other = TestClient(app, cookies={"cz_session": stolen})
    assert other.get("/api/auth/me").status_code == 401


def test_onboarding_requires_care_acknowledgement(app, make_user):
    c = make_user("Asha", onboard=False)
    r = c.post("/api/onboarding", json={"accept_terms_and_care": False, "ai_processing": True})
    assert r.status_code == 422


def test_unauthenticated_access_blocked(app):
    c = TestClient(app)
    for path in ("/api/profile", "/api/checkins", "/api/privacy", "/api/conversations", "/api/privacy/export"):
        assert c.get(path).status_code == 401, path


def test_signup_requires_adult_confirmation(app):
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.headers.update({"X-Conveazy-Client": "web"})
    base = {"email": "teen@example.com", "password": "correct-horse-battery", "display_name": "T"}
    r = c.post("/api/auth/signup", json=base)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "age_required"
    r = c.post("/api/auth/signup", json={**base, "confirm_adult": False})
    assert r.status_code == 400
    r = c.post("/api/auth/signup", json={**base, "confirm_adult": True})
    assert r.status_code == 201
    c.post("/api/onboarding", json={"accept_terms_and_care": True, "ai_processing": False})
    kinds = [h["kind"] for h in c.get("/api/privacy").json()["consent_history"]]
    assert "age_18_plus" in kinds
