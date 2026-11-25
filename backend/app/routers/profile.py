"""Individual communication profile and the optional shared relationship space."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.context import PROFILE_FIELDS, PRIVATE_FIELDS, partner_of
from ..db import get_db
from ..deps import current_user
from ..models import ProfileEntry, Relationship, RelationshipMember, User
from ..schemas import JoinIn, ProfileEntryIn
from ..security import decrypt, encrypt, new_invite_code

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = {e.key: e for e in db.scalars(select(ProfileEntry).where(ProfileEntry.user_id == user.id))}
    return {"fields": [
        {"key": k, "label": label, "value": decrypt(rows[k].value_enc) if k in rows else None,
         "share_with_partner": rows[k].share_with_partner if k in rows else False,
         "use_in_ai": rows[k].use_in_ai if k in rows else False}
        for k, label in PROFILE_FIELDS.items()
    ]}


@router.put("/profile/{key}")
def put_entry(key: str, body: ProfileEntryIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if key not in PROFILE_FIELDS:
        raise HTTPException(404, detail={"code": "unknown_field", "message": "Unknown profile field."})
    e = db.scalar(select(ProfileEntry).where(ProfileEntry.user_id == user.id, ProfileEntry.key == key))
    if not e:
        e = ProfileEntry(user_id=user.id, key=key, value_enc="")
        db.add(e)
    e.value_enc = encrypt(body.value.strip())  # type: ignore[assignment]
    # "My story" is private by design: the partner can never see it, whatever the client sends.
    e.share_with_partner = False if key in PRIVATE_FIELDS else body.share_with_partner
    e.use_in_ai = body.use_in_ai
    db.commit()
    return {"key": key, "share_with_partner": e.share_with_partner, "use_in_ai": e.use_in_ai}


@router.delete("/profile/{key}", status_code=204)
def delete_entry(key: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = db.scalar(select(ProfileEntry).where(ProfileEntry.user_id == user.id, ProfileEntry.key == key))
    if e:
        db.delete(e)
        db.commit()


def _membership(db: Session, user_id: str) -> RelationshipMember | None:
    return db.scalar(select(RelationshipMember).where(RelationshipMember.user_id == user_id))


@router.get("/relationship")
def get_relationship(db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = _membership(db, user.id)
    if not m:
        return {"status": "none"}
    rel = db.get(Relationship, m.relationship_id)
    partner = partner_of(db, user.id)
    if not partner:
        return {"status": "pending", "invite_code": rel.invite_code if rel else None}
    shared = db.scalars(select(ProfileEntry).where(ProfileEntry.user_id == partner.id,
                                                   ProfileEntry.share_with_partner.is_(True))).all()
    return {
        "status": "linked",
        "partner": {"name": partner.display_name, "pronouns": partner.pronouns},
        "partner_shared": [{"key": e.key, "label": PROFILE_FIELDS.get(e.key, e.key), "value": decrypt(e.value_enc)}
                           for e in shared if e.key in PROFILE_FIELDS],
    }


@router.post("/relationship/invite")
def invite(db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = _membership(db, user.id)
    if m:
        rel = db.get(Relationship, m.relationship_id)
        if partner_of(db, user.id):
            raise HTTPException(409, detail={"code": "already_linked", "message": "You're already linked with a partner."})
        return {"invite_code": rel.invite_code}  # type: ignore[union-attr]
    rel = Relationship(created_by=user.id, invite_code=new_invite_code())
    db.add(rel)
    db.flush()
    db.add(RelationshipMember(relationship_id=rel.id, user_id=user.id))
    db.commit()
    return {"invite_code": rel.invite_code}


@router.post("/relationship/join")
def join(body: JoinIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if _membership(db, user.id):
        raise HTTPException(409, detail={"code": "already_in_space", "message": "Leave your current shared space before joining another."})
    rel = db.scalar(select(Relationship).where(Relationship.invite_code == body.code.strip().upper()))
    if not rel or rel.created_by == user.id or len(rel.members) >= 2:
        raise HTTPException(404, detail={"code": "invalid_code", "message": "That invite code isn't valid."})
    db.add(RelationshipMember(relationship_id=rel.id, user_id=user.id))
    rel.invite_code = None  # single-use
    db.commit()
    return get_relationship(db, user)


@router.delete("/relationship", status_code=204)
def leave(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Either partner can end the shared space at any time. Access to shared fields stops immediately."""
    m = _membership(db, user.id)
    if not m:
        return
    rel = db.get(Relationship, m.relationship_id)
    if rel:
        db.delete(rel)
    db.commit()
