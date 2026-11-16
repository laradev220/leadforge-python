"""Integration credential handling."""

from __future__ import annotations

from leadforge_api.core.crypto import decrypt_json, encrypt_json


def test_encrypt_roundtrip() -> None:
    config = {"token": "hs-secret", "nested": {"a": 1}}
    encrypted = encrypt_json(config)
    assert "hs-secret" not in encrypted
    assert decrypt_json(encrypted) == config


def test_ciphertext_differs_each_time() -> None:
    assert encrypt_json({"a": 1}) != encrypt_json({"a": 1})
