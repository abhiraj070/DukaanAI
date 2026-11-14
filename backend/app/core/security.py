"""Security utilities: Password hashing, verification, and authentication tokens."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import get_settings

password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its Argon2 hash."""
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed HMAC-SHA256 token encoding payload data and expiration."""
    settings = get_settings()
    to_encode = data.copy()

    expire = datetime.now(UTC) + (expires_delta if expires_delta else timedelta(days=7))
    to_encode.update({"exp": int(expire.timestamp())})

    payload_bytes = json.dumps(to_encode, sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

    signature = hmac.new(
        settings.APP_SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{payload_b64}.{signature}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Verify signature and expiration, returning decoded payload dict if valid."""
    settings = get_settings()
    parts = token.split(".")
    if len(parts) != 2:
        return None

    payload_b64, signature = parts
    expected_sig = hmac.new(
        settings.APP_SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        return None

    # Add back base64 padding
    padding = len(payload_b64) % 4
    if padding:
        payload_b64 += "=" * (4 - padding)

    try:
        payload_json = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)

        exp = payload.get("exp")
        if exp and datetime.now(UTC).timestamp() > exp:
            return None  # Expired

        return payload
    except Exception:
        return None
