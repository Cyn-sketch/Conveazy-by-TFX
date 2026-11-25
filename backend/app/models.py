"""Database schema. Sensitive free text lives in *_enc columns (Fernet-encrypted)."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    pronouns: Mapped[str | None] = mapped_column(String(40), nullable=True)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    retention_days: Mapped[int] = mapped_column(Integer, default=365)
    save_history: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Consent(Base):
    """Append-only consent ledger. Latest row per (user, kind) is the current state."""
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # age_18_plus | terms_and_care | ai_processing | model_training
    granted: Mapped[bool] = mapped_column(Boolean)
    policy_version: Mapped[str] = mapped_column(String(20), default="2026-11")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Relationship(Base):
    __tablename__ = "relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    invite_code: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    members: Mapped[list["RelationshipMember"]] = relationship(cascade="all, delete-orphan", back_populates="rel")


class RelationshipMember(Base):
    __tablename__ = "relationship_members"
    __table_args__ = (UniqueConstraint("user_id"),)  # MVP: one active relationship per user
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    relationship_id: Mapped[str] = mapped_column(ForeignKey("relationships.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    rel: Mapped[Relationship] = relationship(back_populates="members")


class ProfileEntry(Base):
    """One answer in a person's communication profile. The owner controls both switches."""
    __tablename__ = "profile_entries"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(60))
    value_enc: Mapped[str] = mapped_column(Text)
    share_with_partner: Mapped[bool] = mapped_column(Boolean, default=False)
    use_in_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class CheckIn(Base):
    __tablename__ = "checkins"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    emotion: Mapped[str] = mapped_column(String(30))
    intensity: Mapped[int] = mapped_column(Integer)
    need: Mapped[str] = mapped_column(String(30))
    intent: Mapped[str] = mapped_column(String(20))  # communicate | reflect | break
    note_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module: Mapped[str] = mapped_column(String(20))  # partner | myself | translator
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    messages: Mapped[list["Message"]] = relationship(
        cascade="all, delete-orphan", order_by="Message.created_at", back_populates="conversation"
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user | assistant
    content_enc: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # provider, mode, prompt version, safety flags
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
