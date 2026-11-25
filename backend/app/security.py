"""Password hashing, session tokens and field-level encryption."""
import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerificationError:
        return False
    except Exception:
        return False


def create_token(user_id: str, token_version: int) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "ver": token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.jwt_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _fernet() -> Fernet:
    s = get_settings()
    key = s.data_encryption_key
    if not key:
        # Development fallback: derive a stable key from the JWT secret so local data
        # is still never stored in plaintext. Production refuses to start without a key.
        key = base64.urlsafe_b64encode(hashlib.sha256(("enc:" + s.jwt_secret).encode()).digest()).decode()
    try:
        return Fernet(key.encode())
    except ValueError:
        # Not a Fernet key: treat it as a long passphrase and derive a key from it.
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("enc:" + key).encode()).digest()))


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def new_invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2))
