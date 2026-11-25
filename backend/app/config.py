"""Runtime configuration. Every secret comes from the environment; nothing is hardcoded."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CONVEAZY_", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://conveazy:conveazy@localhost:5432/conveazy"

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        # Hosted Postgres (Neon, Supabase, Vercel Postgres) hands out postgres:// or postgresql:// URLs.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    # Auth
    jwt_secret: str = Field(default="dev-only-change-me-dev-only-change-me", min_length=32)
    jwt_ttl_minutes: int = 60 * 24 * 7
    cookie_secure: bool = False  # set true behind HTTPS in production

    # Field-level encryption at rest (Fernet key, urlsafe base64, 32 bytes).
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    data_encryption_key: str = ""

    # AI providers
    ai_provider: Literal["mock", "openai", "gemini"] = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    ai_timeout_seconds: float = 45.0

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
