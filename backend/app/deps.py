import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Consent, User
from .security import decode_token

COOKIE = "cz_session"
CLIENT_HEADER = "x-conveazy-client"


def csrf_guard(request: Request) -> None:
    """Cookie auth + SameSite=Lax, plus a custom header that cross-site forms cannot set."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CLIENT_HEADER) != "web":
        raise HTTPException(403, detail={"code": "csrf", "message": "Missing client header."})


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    claims = decode_token(token) if token else None
    if not claims:
        raise HTTPException(401, detail={"code": "unauthenticated", "message": "Please sign in."})
    user = db.get(User, claims["sub"])
    if not user or user.token_version != claims.get("ver"):
        raise HTTPException(401, detail={"code": "unauthenticated", "message": "Please sign in again."})
    return user


def consent_state(db: Session, user_id: str) -> dict[str, bool]:
    state: dict[str, bool] = {}
    for c in db.scalars(select(Consent).where(Consent.user_id == user_id).order_by(Consent.created_at)):
        state[c.kind] = c.granted
    return state


def require_ai_consent(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
    if not consent_state(db, user.id).get("ai_processing"):
        raise HTTPException(403, detail={
            "code": "consent_required",
            "message": "AI features need your consent to process what you write. You can turn this on in Privacy.",
        })
    return user


class RateLimiter:
    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = Lock()

    def check(self, key: str, limit: int, window: float = 60.0) -> None:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(429, detail={"code": "rate_limited", "message": "You're going a bit fast. Take a breath and try again in a minute."})
            q.append(now)

    def reset(self) -> None:
        self.hits.clear()


limiter = RateLimiter()


def ai_rate_limit(user: User = Depends(require_ai_consent)) -> User:
    limiter.check(f"ai:{user.id}", get_settings().ai_rate_limit_per_minute)
    return user


def auth_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    limiter.check(f"auth:{ip}", get_settings().auth_rate_limit_per_minute)
