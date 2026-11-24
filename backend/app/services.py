from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import CheckIn, Conversation, User


def purge_expired(db: Session, user: User) -> int:
    """Apply the user's retention window to check-ins and saved conversations."""
    cutoff = datetime.now(UTC) - timedelta(days=user.retention_days)
    n = 0
    n += db.execute(delete(CheckIn).where(CheckIn.user_id == user.id, CheckIn.created_at < cutoff)).rowcount or 0
    old = db.scalars(select(Conversation).where(Conversation.user_id == user.id, Conversation.created_at < cutoff)).all()
    for c in old:
        db.delete(c)
        n += 1
    db.commit()
    return n


def purge_all(db: Session) -> int:
    return sum(purge_expired(db, u) for u in db.scalars(select(User)).all())
