"""Structured output contracts for each module. Every provider response is validated
against these before it reaches a user; anything that fails validation is rejected."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

FlagCategory = Literal[
    "accusatory", "absolute", "dismissive", "defensive", "invalidating",
    "escalating", "mind_reading", "sarcasm", "threat", "contempt",
]
VersionStyle = Literal["gentle", "direct", "reassuring", "boundary", "apologetic", "emotionally_honest"]
EvidenceLevel = Literal["established", "possible", "individual"]


class Flag(BaseModel):
    phrase: str = Field(max_length=300)
    category: FlagCategory
    how_it_may_land: str = Field(max_length=500)


class Version(BaseModel):
    style: VersionStyle
    text: str = Field(min_length=1, max_length=3000)


class Change(BaseModel):
    what: str = Field(max_length=300)
    why: str = Field(max_length=500)


class TranslatorResult(BaseModel):
    intent_summary: str = Field(max_length=600)
    feelings_detected: list[str] = Field(default_factory=list, max_length=8)
    needs_detected: list[str] = Field(default_factory=list, max_length=6)
    flags: list[Flag] = Field(default_factory=list, max_length=12)
    how_original_may_land: str = Field(max_length=800)
    versions: list[Version] = Field(min_length=1, max_length=6)
    changes: list[Change] = Field(default_factory=list, max_length=10)
    preserved: list[str] = Field(default_factory=list, max_length=8)
    boundary_note: str | None = Field(default=None, max_length=500)

    @field_validator("versions")
    @classmethod
    def unique_styles(cls, v: list[Version]) -> list[Version]:
        seen, out = set(), []
        for item in v:
            if item.style not in seen:
                seen.add(item.style)
                out.append(item)
        return out


class EvidencePoint(BaseModel):
    claim: str = Field(max_length=600)
    level: EvidenceLevel
    source_ids: list[str] = Field(default_factory=list, max_length=5)


class PartnerAnswer(BaseModel):
    answer: str = Field(max_length=4000)
    evidence: list[EvidencePoint] = Field(default_factory=list, max_length=8)
    what_cannot_be_inferred: str = Field(max_length=800)
    try_this: list[str] = Field(default_factory=list, max_length=6)
    avoid: list[str] = Field(default_factory=list, max_length=6)
    ask_your_partner: list[str] = Field(default_factory=list, max_length=4)
    professional_help_note: str | None = Field(default=None, max_length=600)


class ReflectionResult(BaseModel):
    situation: str = Field(max_length=800)
    interpretation: str = Field(max_length=800)
    evidence_check: str = Field(max_length=1000)
    alternative_interpretations: list[str] = Field(default_factory=list, max_length=4)
    emotions: list[str] = Field(default_factory=list, max_length=8)
    validation: str = Field(max_length=800)
    possible_needs: list[str] = Field(default_factory=list, max_length=5)
    communication: str = Field(max_length=1500)
    escalation_signs: list[str] = Field(default_factory=list, max_length=5)
    next_step: str = Field(max_length=500)


class Choice(BaseModel):
    choice: str = Field(max_length=300)
    reason: str = Field(max_length=500)
    grounded_in: Literal["their_profile", "evidence", "general"] = "general"


class Avoided(BaseModel):
    pattern: str = Field(max_length=300)
    because: str = Field(max_length=500)


class BridgeResult(BaseModel):
    understood_meaning: str = Field(max_length=1500)
    core_points: list[str] = Field(default_factory=list, max_length=6)
    sender_feelings: list[str] = Field(default_factory=list, max_length=6)
    clarifying_question: str | None = Field(default=None, max_length=400)
    message: str = Field(min_length=1, max_length=3000)
    short_version: str | None = Field(default=None, max_length=800)
    alternatives: list[Version] = Field(default_factory=list, max_length=3)
    why_this_works: list[Choice] = Field(default_factory=list, max_length=6)
    avoided: list[Avoided] = Field(default_factory=list, max_length=6)
    kept_true: list[str] = Field(default_factory=list, max_length=6)
    timing_note: str | None = Field(default=None, max_length=500)
    source_ids: list[str] = Field(default_factory=list, max_length=5)
