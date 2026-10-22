"""
Password hashing and JWT issuance for Provider authentication.

Password hashing uses PBKDF2-HMAC-SHA256 from the standard library rather
than adding a bcrypt/passlib dependency — 260,000 iterations matches
Django's current default, a reasonable modern floor. JWTs use PyJWT
(already a transitive dependency in this environment; pinned explicitly in
requirements.txt) — HS256 signed with settings.secret_key.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

import jwt

from app.core.config import settings
from app.models.mixins import utcnow

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM, password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        algorithm, iterations_str, salt, digest_hex = hashed.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM, password.encode("utf-8"), bytes.fromhex(salt), int(iterations_str)
    )
    return hmac.compare_digest(candidate.hex(), digest_hex)


def create_access_token(provider_id: int, *, expires_minutes: int | None = None) -> str:
    now = utcnow()
    expire_minutes = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    payload = {
        "sub": str(provider_id),
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (or a subclass) on an invalid or expired token."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
