from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _get_fernet() -> Fernet:
    key = get_settings().ENCRYPTION_KEY
    if not key:
        # Generate a throwaway key if none configured (dev mode)
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string; returns a URL-safe base64 token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a token produced by encrypt(); raises ValueError on failure."""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception) as exc:
        raise ValueError("Decryption failed") from exc
