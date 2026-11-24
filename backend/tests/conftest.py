import os

os.environ["CONVEAZY_ENV"] = "test"
os.environ["CONVEAZY_DATABASE_URL"] = "sqlite://"
os.environ["CONVEAZY_AI_PROVIDER"] = "mock"
os.environ["CONVEAZY_AI_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["CONVEAZY_AUTH_RATE_LIMIT_PER_MINUTE"] = "1000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, get_engine, init_engine  # noqa: E402
from app.deps import limiter  # noqa: E402


@pytest.fixture()
def app():
    init_engine("sqlite://")
    from app.main import create_app

    a = create_app()
    yield a
    Base.metadata.drop_all(get_engine())
    limiter.reset()


def _client(app) -> TestClient:
    c = TestClient(app)
    c.headers.update({"X-Conveazy-Client": "web"})
    return c


@pytest.fixture()
def make_user(app):
    def _make(name="Asha", email=None, ai=True, onboard=True):
        c = _client(app)
        email = email or f"{name.lower()}@example.com"
        r = c.post("/api/auth/signup", json={"email": email, "password": "correct-horse-battery", "display_name": name})
        assert r.status_code == 201, r.text
        if onboard:
            r = c.post("/api/onboarding", json={"accept_terms_and_care": True, "ai_processing": ai})
            assert r.status_code == 200, r.text
        return c
    return _make


@pytest.fixture()
def couple(make_user):
    a, b = make_user("Asha"), make_user("Ravi")
    code = a.post("/api/relationship/invite").json()["invite_code"]
    assert b.post("/api/relationship/join", json={"code": code}).status_code == 200
    return a, b
