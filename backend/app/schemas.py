from typing import Literal

from pydantic import model_validator, BaseModel, EmailStr, Field

Emotion = Literal["calm", "anxious", "overwhelmed", "angry", "hurt", "disconnected", "numb", "confused", "frustrated"]
Need = Literal["reassurance", "affection", "clarity", "apology", "space", "listening", "practical_help", "solution"]
Intent = Literal["communicate", "reflect", "break"]


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    pronouns: str | None
    onboarded: bool


class OnboardingIn(BaseModel):
    pronouns: str | None = Field(default=None, max_length=40)
    accept_terms_and_care: bool
    ai_processing: bool
    model_training: bool = False
    retention_days: int = Field(default=365, ge=7, le=3650)
    save_history: bool = True


class ProfileEntryIn(BaseModel):
    value: str = Field(min_length=1, max_length=2000)
    share_with_partner: bool = False
    use_in_ai: bool = False


class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class PrivacyIn(BaseModel):
    retention_days: int | None = Field(default=None, ge=7, le=3650)
    save_history: bool | None = None
    ai_processing: bool | None = None
    model_training: bool | None = None
    share_checkin_signal: bool | None = None


class DeleteAccountIn(BaseModel):
    password: str = Field(max_length=200)
    confirm: Literal["DELETE"]


class CheckInIn(BaseModel):
    emotion: Emotion
    intensity: int = Field(ge=1, le=10)
    need: Need
    intent: Intent
    note: str | None = Field(default=None, max_length=2000)


class TranslateIn(BaseModel):
    draft: str = Field(min_length=1, max_length=4000)
    styles: list[Literal["gentle", "direct", "reassuring", "boundary", "apologetic", "emotionally_honest"]] | None = None
    note: str | None = Field(default=None, max_length=500)
    save: bool = False


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = None


class ReflectIn(BaseModel):
    situation: str = Field(min_length=3, max_length=3000)
    interpretation: str | None = Field(default=None, max_length=2000)
    emotions: list[str] = Field(default_factory=list, max_length=8)
    needs: list[str] = Field(default_factory=list, max_length=6)
    intensity: int | None = Field(default=None, ge=1, le=10)
    save: bool = True


class BridgeIn(BaseModel):
    situation: str = Field(default="", max_length=6000)  # "What happened": enough on its own
    scraps: str = Field(default="", max_length=4000)  # optional rough words
    confirmed_meaning: str | None = Field(default=None, max_length=1500)
    include_feelings: bool = False
    intensity: int | None = Field(default=None, ge=1, le=10)  # the sender's own rating, shown in the brief
    share_traits: bool = False  # trait suggestions stay private unless the sender opts in
    traits: list[dict] = Field(default_factory=list, max_length=3)
    save: bool = False

    @model_validator(mode="after")
    def _need_something(self):
        if not self.situation.strip() and not self.scraps.strip():
            raise ValueError("Tell CONVEAZY what happened, or what you want to say.")
        return self
