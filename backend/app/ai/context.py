"""Personal context engine.

Returns ONLY context the owner has consented to: their own entries marked `use_in_ai`,
and their partner's entries marked BOTH `share_with_partner` and `use_in_ai`.
Private drafts, reflections and check-ins of the partner are never read here.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CheckIn, ProfileEntry, RelationshipMember, User
from ..security import decrypt

PROFILE_FIELDS: dict[str, str] = {
    "about_me": "About me, in my own words",
    "my_triggers": "What can trigger me",
    "what_calms_me": "What calms me down",
    "how_i_express_myself": "How I express myself (and where I struggle)",
    "communication_style": "How I tend to communicate",
    "reassurance_looks_like": "What reassurance looks like to me",
    "feel_dismissed_when": "I feel dismissed when",
    "common_misunderstandings": "Misunderstandings we often have",
    "boundaries": "My boundaries",
    "resolve_disagreements": "How I prefer to resolve disagreements",
    "receive_affection": "How I like to receive affection",
    "overwhelmed_helps": "When I'm overwhelmed, this helps",
    "overwhelmed_doesnt_help": "When I'm overwhelmed, this doesn't help",
    "self_disclosed_context": "Diagnoses or health context I choose to share (optional)",
}


def partner_of(db: Session, user_id: str) -> User | None:
    mine = db.scalar(select(RelationshipMember).where(RelationshipMember.user_id == user_id))
    if not mine:
        return None
    other = db.scalar(
        select(RelationshipMember).where(
            RelationshipMember.relationship_id == mine.relationship_id, RelationshipMember.user_id != user_id
        )
    )
    return db.get(User, other.user_id) if other else None


def _entries(db: Session, user_id: str, *, require_shared: bool) -> dict[str, str]:
    q = select(ProfileEntry).where(ProfileEntry.user_id == user_id, ProfileEntry.use_in_ai.is_(True))
    if require_shared:
        q = q.where(ProfileEntry.share_with_partner.is_(True))
    out = {}
    for e in db.scalars(q):
        val = decrypt(e.value_enc)
        if val and e.key in PROFILE_FIELDS:
            out[PROFILE_FIELDS[e.key]] = val
    return out


def latest_checkin(db: Session, user_id: str, hours: int = 6) -> CheckIn | None:
    ci = db.scalar(select(CheckIn).where(CheckIn.user_id == user_id).order_by(CheckIn.created_at.desc()).limit(1))
    if ci and ci.created_at.replace(tzinfo=ci.created_at.tzinfo or UTC) >= datetime.now(UTC) - timedelta(hours=hours):
        return ci
    return None


def partner_checkin_signal(db: Session, partner: User) -> dict | None:
    """Only the feeling and intensity of the partner's latest check-in, and only if they
    opted in with the `share_checkin_signal` consent. Never the note."""
    from ..deps import consent_state

    if not consent_state(db, partner.id).get("share_checkin_signal"):
        return None
    ci = latest_checkin(db, partner.id)
    return {"feeling": ci.emotion, "intensity": ci.intensity} if ci else None


def build_personal_context(db: Session, user: User, checkin_id: str | None = None) -> dict:
    ctx: dict = {"you": {"name": user.display_name, "preferences": _entries(db, user.id, require_shared=False)}}
    partner = partner_of(db, user.id)
    if partner:
        ctx["partner"] = {
            "name": partner.display_name,
            "preferences_they_chose_to_share": _entries(db, partner.id, require_shared=True),
        }
    ci = None
    if checkin_id:
        ci = db.scalar(select(CheckIn).where(CheckIn.id == checkin_id, CheckIn.user_id == user.id))
    else:
        since = datetime.now(UTC) - timedelta(hours=6)
        ci = db.scalar(
            select(CheckIn).where(CheckIn.user_id == user.id).order_by(CheckIn.created_at.desc()).limit(1)
        )
        if ci and ci.created_at.replace(tzinfo=ci.created_at.tzinfo or UTC) < since:
            ci = None
    if ci:
        ctx["your_recent_checkin"] = {
            "feeling": ci.emotion, "intensity": f"{ci.intensity}/10", "intensity_value": ci.intensity, "need": ci.need, "wants_to": ci.intent,
        }
    return ctx
