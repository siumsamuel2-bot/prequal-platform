"""Coverage for app.services.encryption_service (MID-676).

Exercises the field-level encryption used for PII / client data:

* key derivation (``ENCRYPTION_KEY`` present, absent -> dev fallback),
* the cached Fernet handle,
* local encrypt/decrypt round-trip plus the None/empty short-circuits,
* the re-raise paths when encryption/decryption fails,
* the AWS KMS branches (success, ``boto3`` missing, KMS call failure and the
  local fallback) with a fake ``boto3`` injected via ``sys.modules``.

No real KMS or network is used.
"""
from __future__ import annotations

import base64
import sys
from types import SimpleNamespace

import pytest

from app.services import encryption_service as enc

KEY = "unit-test-encryption-key-material"


@pytest.fixture(autouse=True)
def _reset_fernet():
    """Clear the module-level cached Fernet between tests."""
    enc._fernet = None
    yield
    enc._fernet = None


class _FakeKMSClient:
    def __init__(self, *, encrypt_error=None, decrypt_error=None):
        self._encrypt_error = encrypt_error
        self._decrypt_error = decrypt_error
        self.encrypt_calls = []
        self.decrypt_calls = []

    def encrypt(self, **kwargs):
        self.encrypt_calls.append(kwargs)
        if self._encrypt_error:
            raise self._encrypt_error
        return {"CiphertextBlob": b"encrypted-blob"}

    def decrypt(self, **kwargs):
        self.decrypt_calls.append(kwargs)
        if self._decrypt_error:
            raise self._decrypt_error
        return {"Plaintext": b"the-plaintext"}


def _install_boto3(monkeypatch, client):
    fake = SimpleNamespace(client=lambda name, region_name=None: client)
    monkeypatch.setitem(sys.modules, "boto3", fake)
    return client


# ---------------------------------------------------------------------------
# Key derivation / Fernet cache
# ---------------------------------------------------------------------------

def test_get_fernet_key_derives_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", KEY)
    key_a = enc._get_fernet_key()
    key_b = enc._get_fernet_key()
    assert key_a == key_b
    # base64.urlsafe_b64encode of 32 bytes -> 44 chars, decodes to 32 bytes.
    assert len(key_a) == 44
    assert len(base64.urlsafe_b64decode(key_a)) == 32


def test_get_fernet_key_dev_fallback_without_env(monkeypatch) -> None:
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    key = enc._get_fernet_key()
    assert len(base64.urlsafe_b64decode(key)) == 32


def test_get_fernet_caches_instance(monkeypatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", KEY)
    first = enc._get_fernet()
    assert enc._get_fernet() is first


# ---------------------------------------------------------------------------
# Local encrypt / decrypt
# ---------------------------------------------------------------------------

def test_encrypt_value_none_and_empty() -> None:
    assert enc.encrypt_value(None) is None
    assert enc.encrypt_value("") is None


def test_decrypt_value_none_and_empty() -> None:
    assert enc.decrypt_value(None) is None
    assert enc.decrypt_value("") is None


def test_local_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", KEY)
    monkeypatch.setattr(enc, "USE_KMS", False)
    token = enc.encrypt_value("Jane Doe SSN 000-00-0000")
    assert token is not None and token != "Jane Doe SSN 000-00-0000"
    assert enc.decrypt_value(token) == "Jane Doe SSN 000-00-0000"


def test_encrypt_value_reraises_failure(monkeypatch) -> None:
    monkeypatch.setattr(enc, "USE_KMS", False)

    def _boom(_plaintext):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(enc, "_encrypt_local", _boom)
    with pytest.raises(RuntimeError, match="kaboom"):
        enc.encrypt_value("secret")


def test_decrypt_value_reraises_failure(monkeypatch) -> None:
    def _boom(_ciphertext):
        raise RuntimeError("bad token")

    monkeypatch.setattr(enc, "_decrypt_local", _boom)
    with pytest.raises(RuntimeError, match="bad token"):
        enc.decrypt_value("not-a-token")


# ---------------------------------------------------------------------------
# KMS branches
# ---------------------------------------------------------------------------

def test_encrypt_kms_success(monkeypatch) -> None:
    monkeypatch.setattr(enc, "USE_KMS", True)
    monkeypatch.setattr(enc, "AWS_KMS_KEY_ID", "key-123")
    client = _install_boto3(monkeypatch, _FakeKMSClient())
    out = enc.encrypt_value("top secret")
    assert out == "aws:" + base64.b64encode(b"encrypted-blob").decode()
    assert client.encrypt_calls[0]["KeyId"] == "key-123"
    assert client.encrypt_calls[0]["Plaintext"] == b"top secret"


def test_encrypt_kms_import_error_falls_back_local(monkeypatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", KEY)
    monkeypatch.setattr(enc, "USE_KMS", True)
    monkeypatch.setitem(sys.modules, "boto3", None)  # `import boto3` -> ImportError
    out = enc._encrypt_kms("fallback please")
    assert not out.startswith("aws:")
    assert enc._decrypt_local(out) == "fallback please"


def test_encrypt_kms_error_falls_back_local(monkeypatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", KEY)
    monkeypatch.setattr(enc, "USE_KMS", True)
    _install_boto3(monkeypatch, _FakeKMSClient(encrypt_error=RuntimeError("kms down")))
    out = enc._encrypt_kms("fallback please")
    assert not out.startswith("aws:")
    assert enc._decrypt_local(out) == "fallback please"


def test_decrypt_kms_success(monkeypatch) -> None:
    monkeypatch.setattr(enc, "USE_KMS", True)
    client = _install_boto3(monkeypatch, _FakeKMSClient())
    payload = "aws:" + base64.b64encode(b"ciphertext-bytes").decode()
    assert enc.decrypt_value(payload) == "the-plaintext"
    assert client.decrypt_calls[0]["CiphertextBlob"] == b"ciphertext-bytes"


def test_decrypt_kms_non_aws_prefix_uses_local(monkeypatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", KEY)
    monkeypatch.setattr(enc, "USE_KMS", True)
    token = enc._encrypt_local("local path value")
    # No "aws:" prefix, so KMS is skipped even when USE_KMS is on.
    assert enc.decrypt_value(token) == "local path value"


def test_decrypt_kms_import_error_raises(monkeypatch) -> None:
    monkeypatch.setattr(enc, "USE_KMS", True)
    monkeypatch.setitem(sys.modules, "boto3", None)
    payload = "aws:" + base64.b64encode(b"blob").decode()
    with pytest.raises(ImportError):
        enc.decrypt_value(payload)


def test_decrypt_kms_error_raises(monkeypatch) -> None:
    monkeypatch.setattr(enc, "USE_KMS", True)
    _install_boto3(monkeypatch, _FakeKMSClient(decrypt_error=RuntimeError("kms down")))
    payload = "aws:" + base64.b64encode(b"blob").decode()
    with pytest.raises(RuntimeError, match="kms down"):
        enc.decrypt_value(payload)
