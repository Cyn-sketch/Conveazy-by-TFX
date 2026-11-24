"""Onboarding, privacy settings, consent ledger, data export and account deletion."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import COOKIE, consent_state, current_user
from ..models import CheckIn, Consent, Conversation, ProfileEntry, RelationshipMember, User
from ..schemas import DeleteAccountIn, OnboardingIn, PrivacyIn
from ..security import decrypt, verify_password
from .auth import user_out

router = APIRouter(prefix="/api", tags=["account"])


def _record(db: Session, user_id: str, kind: str, granted: bool) -> None:
    db.add(Consent(user_id=user_id, kind=kind, granted=granted))


@router.post("/onboarding")
def onboarding(body: OnboardingIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not body.accept_terms_and_care:
        raise HTTPException(422, detail={"code": "terms_required",
                                         "message": "Please confirm you understand CONVEAZY complements, and doesn't replace, professional care."})
    user.pronouns = body.pronouns or None
    user.retention_days = body.retention_days
    user.save_history = body.save_history
    user.onboarded = True
    _record(db, user.id, "terms_and_care", True)
    _record(db, user.id, "ai_processing", body.ai_processing)
    _record(db, user.id, "model_training", body.model_training)
    db.commit()
    return user_out(user)


@router.get("/privacy")
def get_privacy(db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = consent_state(db, user.id)
    shared = db.scalars(select(ProfileEntry.key).where(ProfileEntry.user_id == user.id,
                                                       ProfileEntry.share_with_partner.is_(True))).all()
    return {
        "retention_days": user.retention_days,
        "save_history": user.save_history,
        "consents": {k: c.get(k, False) for k in ("terms_and_care", "ai_processing", "model_training", "share_checkin_signal")},
        "partner_can_see": {
            "profile_fields": list(shared),
            "checkins": False, "checkin_signal_to_partner_ai": c.get("share_checkin_signal", False), "drafts": False, "reflections": False, "conversations": False,
        },
        "consent_history": [
            {"kind": x.kind, "granted": x.granted, "at": x.created_at.isoformat(), "policy_version": x.policy_version}
            for x in db.scalars(select(Consent).where(Consent.user_id == user.id).order_by(Consent.created_at.desc()))
        ],
    }


@router.put("/privacy")
def put_privacy(body: PrivacyIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if body.retention_days is not None:
        user.retention_days = body.retention_days
    if body.save_history is not None:
        user.save_history = body.save_history
    current = consent_state(db, user.id)
    for kind in ("ai_processing", "model_training", "share_checkin_signal"):
        val = getattr(body, kind)
        if val is not None and current.get(kind) != val:
            _record(db, user.id, kind, val)
    db.commit()
    return get_privacy(db, user)


@router.get("/privacy/export")
def export(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Everything we hold about you, decrypted, as JSON. Contains nothing of your partner's."""
    convs = db.scalars(select(Conversation).where(Conversation.user_id == user.id)).all()
    data = {
        "exported_at": datetime.now(UTC).isoformat(),
        "account": {"email": user.email, "display_name": user.display_name, "pronouns": user.pronouns,
                    "created_at": user.created_at.isoformat(), "retention_days": user.retention_days,
                    "save_history": user.save_history},
        "consents": [{"kind": c.kind, "granted": c.granted, "at": c.created_at.isoformat()}
                     for c in db.scalars(select(Consent).where(Consent.user_id == user.id))],
        "profile": [{"key": e.key, "value": decrypt(e.value_enc), "share_with_partner": e.share_with_partner,
                     "use_in_ai": e.use_in_ai} for e in db.scalars(select(ProfileEntry).where(ProfileEntry.user_id == user.id))],
        "checkins": [{"emotion": c.emotion, "intensity": c.intensity, "need": c.need, "intent": c.intent,
                      "note": decrypt(c.note_enc), "at": c.created_at.isoformat()}
                     for c in db.scalars(select(CheckIn).where(CheckIn.user_id == user.id))],
        "conversations": [{"module": c.module, "title": c.title, "created_at": c.created_at.isoformat(),
                           "messages": [{"role": m.role, "content": decrypt(m.content_enc), "meta": m.meta,
                                         "at": m.created_at.isoformat()} for m in c.messages]} for c in convs],
    }
    return Response(
        content=__import__("json").dumps(data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="conveazy-export.json"'},
    )


@router.delete("/account", status_code=204)
def delete_account(body: DeleteAccountIn, resp: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(403, detail={"code": "bad_password", "message": "Password didn't match."})
    # Explicit deletes so this works even where the database doesn't enforce cascades.
    for model in (CheckIn, ProfileEntry, Consent, RelationshipMember):
        for row in db.scalars(select(model).where(model.user_id == user.id)).all():
            db.delete(row)
    for c in db.scalars(select(Conversation).where(Conversation.user_id == user.id)).all():
        db.delete(c)
    from ..models import Relationship
    for r in db.scalars(select(Relationship).where(Relationship.created_by == user.id)).all():
        db.delete(r)
    db.delete(user)
    db.commit()
    resp.delete_cookie(COOKIE, path="/")
