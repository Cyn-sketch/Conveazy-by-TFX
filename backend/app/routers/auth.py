from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import COOKIE, auth_rate_limit, current_user
from ..models import Consent, User
from ..schemas import LoginIn, SignupIn, UserOut
from ..security import create_token, hash_password, verify_password
from ..services import purge_expired

router = APIRouter(prefix="/api/auth", tags=["auth"])
_DUMMY_HASH = hash_password("timing-equaliser-not-a-password")


def _set_session(resp: Response, user: User) -> None:
    s = get_settings()
    resp.set_cookie(
        COOKIE, create_token(user.id, user.token_version), httponly=True, secure=s.cookie_secure,
        samesite="lax", max_age=s.jwt_ttl_minutes * 60, path="/",
    )


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, display_name=u.display_name, pronouns=u.pronouns, onboarded=u.onboarded)


@router.post("/signup", response_model=UserOut, status_code=201, dependencies=[Depends(auth_rate_limit)])
def signup(body: SignupIn, resp: Response, db: Session = Depends(get_db)):
    if not body.confirm_adult:
        raise HTTPException(400, detail={"code": "age_required",
                                         "message": "CONVEAZY is for adults. Please confirm you are 18 or older."})
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, detail={"code": "email_taken", "message": "An account with that email already exists."})
    user = User(email=email, password_hash=hash_password(body.password), display_name=body.display_name.strip(),
                retention_days=get_settings().default_retention_days)
    db.add(user)
    db.flush()
    db.add(Consent(user_id=user.id, kind="age_18_plus", granted=True))
    db.commit()
    _set_session(resp, user)
    return user_out(user)


@router.post("/login", response_model=UserOut, dependencies=[Depends(auth_rate_limit)])
def login(body: LoginIn, resp: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        raise HTTPException(401, detail={"code": "bad_credentials", "message": "That email and password don't match."})
    purge_expired(db, user)
    _set_session(resp, user)
    return user_out(user)


@router.post("/logout", status_code=204)
def logout(resp: Response, everywhere: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if everywhere:
        user.token_version += 1
        db.commit()
    resp.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user)
