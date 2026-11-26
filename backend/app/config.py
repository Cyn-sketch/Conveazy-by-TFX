"""Runtime configuration. Every secret comes from the environment; nothing is hardcoded."""
from functools import lru_cache
from typing import Literal

import os

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CONVEAZY_", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    # Also picks up the variables Vercel's Neon / Postgres integrations create on their own.
    database_url: str = Field(
        default="postgresql+psycopg://conveazy:conveazy@localhost:5432/conveazy",
        validation_alias=AliasChoices("CONVEAZY_DATABASE_URL", "DATABASE_URL", "POSTGRES_URL"),
    )

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        # Hosted Postgres (Neon, Supabase, Vercel Postgres) hands out postgres:// or postgresql:// URLs.
        v = v.strip()
        if v.startswith("psql "):  # copied from Neon's "psql" snippet
            v = v[5:].strip()
        v = v.strip("'\"")
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @model_validator(mode="after")
    def _prefixed_integration_url(self):
        # Vercel's Storage integrations may add a custom prefix (e.g. STORAGE_DATABASE_URL).
        if "@localhost:" in self.database_url:
            for name in sorted(os.environ):
                if name.endswith(("_DATABASE_URL", "_POSTGRES_URL")) and not name.endswith("UNPOOLED_DATABASE_URL") \
                        and os.environ[name].startswith(("postgres://", "postgresql://")):
                    self.database_url = type(self)._psycopg_driver(os.environ[name])
                    break
        return self

    @field_validator("ai_provider", mode="before")
    @classmethod
    def _provider_name(cls, v):
        # Be forgiving: "Gemini", " gemini ", "google gemini" all mean gemini. Anything unrecognised
        # falls back to choosing by whichever key is present, instead of taking the whole app down.
        if not isinstance(v, str):
            return v
        t = v.strip().strip("'\"").lower()
        if "gemini" in t or "google" in t:
            return "gemini"
        if "openai" in t or "gpt" in t:
            return "openai"
        if t == "mock":
            return "mock"
        return "auto"

    @field_validator("openai_api_key", "gemini_api_key")
    @classmethod
    def _strip_key(cls, v: str) -> str:
        return v.strip().strip("'\"")

    @model_validator(mode="after")
    def _provider_from_key(self):
        # A key with no provider chosen means "use that key"; an explicit CONVEAZY_AI_PROVIDER=mock still wins.
        if "ai_provider" not in self.model_fields_set or self.ai_provider == "auto":
            self.ai_provider = "mock"
            if self.gemini_api_key:
                self.ai_provider = "gemini"
            elif self.openai_api_key:
                self.ai_provider = "openai"
        return self

    # Auth
    jwt_secret: str = Field(default="dev-only-change-me-dev-only-change-me", min_length=32)
    jwt_ttl_minutes: int = 60 * 24 * 7
    cookie_secure: bool = False  # set true behind HTTPS in production

    # Field-level encryption at rest (Fernet key, urlsafe base64, 32 bytes).
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    data_encryption_key: str = ""

    # AI providers
    # The unprefixed names are accepted too, since they are what people usually type in a host's settings.
    ai_provider: Literal["mock", "openai", "gemini", "auto"] = Field(
        default="mock", validation_alias=AliasChoices("CONVEAZY_AI_PROVIDER", "AI_PROVIDER"))
    openai_api_key: str = Field(default="", validation_alias=AliasChoices("CONVEAZY_OPENAI_API_KEY", "OPENAI_API_KEY"))
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = Field(
        default="", validation_alias=AliasChoices("CONVEAZY_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"))
    gemini_model: str = "gemini-flash-latest"  # Google's alias for the current Flash model
    ai_timeout_seconds: float = 35.0  # per model try; writing the full message can take Gemini ~20-30 s
    # Backup models tried when the main one is busy (comma-separated); more are found automatically.
    gemini_fallback_models: str = "gemini-flash-lite-latest"

    # Abuse protection
    ai_rate_limit_per_minute: int = 12
    auth_rate_limit_per_minute: int = 10

    default_retention_days: int = 365

    def validate_for_production(self) -> None:
        if self.env != "production":
            return
        problems = []
        if self.jwt_secret.startswith("dev-only"):
            problems.append("CONVEAZY_JWT_SECRET must be set")
        if not self.data_encryption_key:
            problems.append("CONVEAZY_DATA_ENCRYPTION_KEY must be set")
        else:
            try:
                from cryptography.fernet import Fernet
                Fernet(self.data_encryption_key.encode())
            except Exception:  # noqa: BLE001
                # A long random passphrase also works; a key is derived from it.
                if len(self.data_encryption_key) < 32:
                    problems.append("CONVEAZY_DATA_ENCRYPTION_KEY must be a Fernet key or a random passphrase of 32+ characters")
        if not self.cookie_secure:
            problems.append("CONVEAZY_COOKIE_SECURE must be true")
        if problems:
            raise RuntimeError("Unsafe production config: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
