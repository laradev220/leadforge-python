"""Symmetric encryption for integration credentials."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from leadforge_config import get_settings

from leadforge_api.core.errors import bad_request


def _fernet() -> Fernet:
    settings = get_settings()
    secret = settings.integrations_secret or settings.jwt_secret
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_json(data: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_json(value: str) -> dict[str, Any]:
    try:
        return json.loads(_fernet().decrypt(value.encode()).decode())
    except (InvalidToken, ValueError) as exc:
        raise bad_request("Stored integration credentials are unreadable") from exc
