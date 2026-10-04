"""Tests for runtime secrets loading (MID-594).

These tests exercise the caching / fallback behaviour without touching AWS by
injecting a fake Secrets Manager client.
"""

import os

import pytest

from app.services import secrets_manager as sm

_HYDRATED_VARS = ("SECRET_KEY", "ENCRYPTION_KEY", "SMTP_PORT", "SMTP_HOST")


@pytest.fixture(autouse=True)
def _clean_env():
    """Keep hydrated env vars from leaking between tests."""
    snapshot = {k: os.environ.get(k) for k in _HYDRATED_VARS}
    for key in _HYDRATED_VARS:
        os.environ.pop(key, None)
    yield
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


class FakeClient:
    """Minimal stand-in for ``boto3.client('secretsmanager')``."""

    def __init__(self, values):
        self.values = values
        self.calls = []

    def get_secret_value(self, SecretId):  # noqa: N803 - boto3 signature
        self.calls.append(SecretId)
        if SecretId not in self.values:
            raise RuntimeError("ResourceNotFoundException")
        return {"SecretString": self.values[SecretId]}


def make_manager(values):
    manager = sm.SecretsManager(enabled=True)
    manager._client = FakeClient(values)
    return manager


def test_get_secret_prefers_environment(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "from-env")
    manager = make_manager({"prequal/stripe-secrets": '{"STRIPE_SECRET_KEY": "from-vault"}'})

    assert manager.get_secret("STRIPE_SECRET_KEY") == "from-env"
    # Environment hit must not touch the vault.
    assert manager._client.calls == []


def test_get_secret_reads_plain_string_and_caches():
    manager = make_manager({"prequal/single": "s3cret-value"})

    assert manager.get_secret("prequal/single") == "s3cret-value"
    assert manager.get_secret("prequal/single") == "s3cret-value"
    assert manager._client.calls == ["prequal/single"]


def test_get_secrets_expands_json_payload():
    payload = '{"SECRET_KEY": "abc", "ENCRYPTION_KEY": "def", "SMTP_PORT": 587}'
    manager = make_manager({"prequal/api-secrets": payload})

    secrets = manager.get_secrets("prequal/api-secrets")

    assert secrets["SECRET_KEY"] == "abc"
    assert secrets["ENCRYPTION_KEY"] == "def"
    assert secrets["SMTP_PORT"] == "587"


def test_hydrate_environment_sets_missing_vars(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    payload = '{"SECRET_KEY": "vault-secret", "ENCRYPTION_KEY": "vault-key"}'
    manager = make_manager({"prequal/api-secrets": payload})

    populated = manager.hydrate_environment(["prequal/api-secrets"])

    assert set(populated) == {"SECRET_KEY", "ENCRYPTION_KEY"}
    assert os.environ["SECRET_KEY"] == "vault-secret"
    assert os.environ["ENCRYPTION_KEY"] == "vault-key"


def test_hydrate_environment_does_not_override_existing(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "already-set")
    payload = '{"SECRET_KEY": "vault-secret", "ENCRYPTION_KEY": "vault-key"}'
    manager = make_manager({"prequal/api-secrets": payload})

    populated = manager.hydrate_environment(["prequal/api-secrets"])

    assert populated == ["ENCRYPTION_KEY"]
    assert os.environ["SECRET_KEY"] == "already-set"


def test_disabled_manager_has_no_side_effects(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    manager = sm.SecretsManager(enabled=False)

    assert manager.hydrate_environment(["prequal/api-secrets"]) == []
    assert manager.get_secret("anything", default="fallback") == "fallback"
    assert "SECRET_KEY" not in os.environ


def test_refresh_invalidates_cache():
    manager = make_manager({"prequal/single": "first"})

    assert manager.get_secret("prequal/single") == "first"
    manager.refresh("prequal/single")
    manager._client.values["prequal/single"] = "second"

    assert manager.get_secret("prequal/single") == "second"
    assert manager._client.calls == ["prequal/single", "prequal/single"]


def test_missing_secret_returns_default():
    manager = make_manager({})

    assert manager.get_secret("prequal/absent", default="fallback") == "fallback"


def test_parse_secret_payload_handles_plain_and_malformed():
    assert sm._parse_secret_payload("plain") == {"value": "plain"}
    assert sm._parse_secret_payload("{not-json") == {"value": "{not-json"}
    assert sm._parse_secret_payload("") == {}
    assert sm._parse_secret_payload('{"A": null}') == {"A": ""}
