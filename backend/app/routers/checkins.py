from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.safety import crisis_payload, screen_input
from ..db import get_db
from ..deps import current_user
from ..models import CheckIn, User
from ..schemas import CheckInIn
from ..security import decrypt, encrypt

router = APIRouter(prefix="/api/checkins", tags=["checkins"])

SUGGESTIONS = {
    "communicate": {"label": "Write it out together", "href": "/app/translate"},
    "reflect": {"label": "Reflect privately first", "href": "/app/myself"},
    "break": {"label": "Take a break", "href": None},
}


def _out(c: CheckIn) -> dict:
    return {"id": c.id, "emotion": c.emotion, "intensity": c.intensity, "need": c.need, "intent": c.intent,
            "note": decrypt(c.note_enc), "created_at": c.created_at.isoformat()}


@router.post("", status_code=201)
def create(body: CheckInIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = CheckIn(user_id=user.id, emotion=body.emotion, intensity=body.intensity, need=body.need,
                intent=body.intent, note_enc=encrypt(body.note) if body.note else None)
    db.add(c)
    db.commit()
    screen = screen_input(body.note)
    intent = body.intent
    guidance = None
    if body.intensity >= 8 and intent == "communicate":
        guidance = ("Your intensity is high right now. Many people find it helps to take 20 minutes to settle "
                    "before sending anything important. Your feelings will still be valid in 20 minutes.")
    return {
        "checkin": _out(c),
        "next": SUGGESTIONS[intent],
        "guidance": guidance,
        "crisis": crisis_payload(screen.crisis) if screen.crisis != "none" else None,
        "disclaimer": "Check-ins are a private note to yourself, not an assessment.",
    }


@router.get("")
def list_mine(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(CheckIn).where(CheckIn.user_id == user.id).order_by(CheckIn.created_at.desc()).limit(50))
    return {"checkins": [_out(c) for c in rows]}


@router.delete("/{checkin_id}", status_code=204)
def delete(checkin_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.scalar(select(CheckIn).where(CheckIn.id == checkin_id, CheckIn.user_id == user.id))
    if not c:
        raise HTTPException(404, detail={"code": "not_found", "message": "Not found."})
    db.delete(c)
    db.commit()
