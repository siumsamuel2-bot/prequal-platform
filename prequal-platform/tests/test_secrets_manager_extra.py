"""Coverage for app.services.secrets_manager (MID-676).

Exercises the runtime secrets loader:

* ``_is_truthy`` / ``_parse_secret_payload`` normalisation,
* ``SecretsManager`` construction, the ``enabled`` gate and the lazy, locked
  client creation (success, missing ``boto3``, client-creation failure),
* ``get_secret`` resolution order (env > vault > default),
* ``get_secrets`` + ``refresh`` cache behaviour,
* ``hydrate_environment`` (plain + JSON payloads, never overwriting env,
  disabling when not enabled) and the module-level wrapper.

A fake ``boto3`` is injected via ``sys.modules``; no AWS access.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

from app.services import secrets_manager as sm


class _FakeSMClient:
    def __init__(self, payloads):
        self._payloads = payloads
        self.calls = []

    def get_secret_value(self, SecretId):
        self.calls.append(SecretId)
        return {"SecretString": self._payloads[SecretId]}


def _install_boto3(monkeypatch, client):
    fake = SimpleNamespace(client=lambda name, region_name=None: client)
    monkeypatch.setitem(sys.modules, "boto3", fake)
    return client


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [("1", True), ("true", True), ("YES", True), (" on ", True),
     ("0", False), ("no", False), ("", False), (None, False)],
)
def test_is_truthy(value, expected) -> None:
    assert sm._is_truthy(value) is expected


def test_parse_secret_payload_variants() -> None:
    assert sm._parse_secret_payload("") == {}
    assert sm._parse_secret_payload("   ") == {}
    assert sm._parse_secret_payload("plain-secret") == {"value": "plain-secret"}
    assert sm._parse_secret_payload('{"A": "1", "B": null}') == {"A": "1", "B": ""}
    # Looks like JSON but is malformed -> wrapped as a plain value.
    assert sm._parse_secret_payload('{"A": ') == {"value": '{"A":'}
    # Valid JSON that is not an object -> wrapped as a plain value.
    assert sm._parse_secret_payload("[1, 2]") == {"value": "[1, 2]"}


# ---------------------------------------------------------------------------
# Construction / client creation
# ---------------------------------------------------------------------------

def test_constructor_reads_env(monkeypatch) -> None:
    monkeypatch.setenv(sm.REGION_ENV, "eu-west-1")
    monkeypatch.setenv(sm.ENABLED_ENV, "yes")
    mgr = sm.SecretsManager()
    assert mgr.enabled is True
    assert mgr._region == "eu-west-1"


def test_disabled_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv(sm.ENABLED_ENV, raising=False)
    assert sm.SecretsManager().enabled is False


def test_get_client_missing_boto3_disables(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "boto3", None)
    mgr = sm.SecretsManager(enabled=True)
    assert mgr._get_client() is None
    assert mgr.enabled is False


def test_get_client_success_and_cached(monkeypatch) -> None:
    client = _install_boto3(monkeypatch, _FakeSMClient({}))
    mgr = sm.SecretsManager(region="us-east-1", enabled=True)
    assert mgr._get_client() is client
    # Second call short-circuits on the cached client.
    assert mgr._get_client() is client


def test_get_client_creation_failure_disables(monkeypatch) -> None:
    def _boom(name, region_name=None):
        raise RuntimeError("bad region")

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=_boom))
    mgr = sm.SecretsManager(enabled=True)
    assert mgr._get_client() is None
    assert mgr.enabled is False


# ---------------------------------------------------------------------------
# get_secret / get_secrets / refresh
# ---------------------------------------------------------------------------

def test_get_secret_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("MY_SECRET", "from-env")
    mgr = sm.SecretsManager(enabled=True)
    assert mgr.get_secret("MY_SECRET") == "from-env"


def test_get_secret_default_when_disabled(monkeypatch) -> None:
    monkeypatch.delenv("MISSING_SECRET", raising=False)
    mgr = sm.SecretsManager(enabled=False)
    assert mgr.get_secret("MISSING_SECRET") is None
    assert mgr.get_secret("MISSING_SECRET", default="fallback") == "fallback"


def test_get_secret_from_vault(monkeypatch) -> None:
    monkeypatch.delenv("VAULTED", raising=False)
    client = _install_boto3(monkeypatch, _FakeSMClient({"VAULTED": '{"value": "vault-value"}'}))
    mgr = sm.SecretsManager(enabled=True)
    assert mgr.get_secret("VAULTED") == "vault-value"
    assert client.calls == ["VAULTED"]
    # Cached on the second call.
    assert mgr.get_secret("VAULTED") == "vault-value"
    assert client.calls == ["VAULTED"]


def test_get_secrets_and_refresh(monkeypatch) -> None:
    monkeypatch.delenv("CONFIG", raising=False)
    client = _install_boto3(monkeypatch, _FakeSMClient({"CONFIG": '{"A": "1", "B": "2"}'}))
    mgr = sm.SecretsManager(enabled=True)
    assert mgr.get_secrets("CONFIG") == {"A": "1", "B": "2"}
    mgr.refresh("CONFIG")
    assert mgr.get_secrets("CONFIG") == {"A": "1", "B": "2"}
    assert client.calls == ["CONFIG", "CONFIG"]
    mgr.refresh()  # clear all
    assert mgr._cache == {}


def test_load_payload_when_disabled() -> None:
    assert sm.SecretsManager(enabled=False)._load_payload("X") == {}


def test_load_payload_client_none(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "boto3", None)
    mgr = sm.SecretsManager(enabled=True)
    assert mgr._load_payload("X") == {}


# ---------------------------------------------------------------------------
# hydrate_environment
# ---------------------------------------------------------------------------

def test_hydrate_disabled_returns_empty() -> None:
    assert sm.SecretsManager(enabled=False).hydrate_environment(["X"]) == []


def test_hydrate_plain_and_json_payloads(monkeypatch) -> None:
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    _install_boto3(
        monkeypatch,
        _FakeSMClient(
            {
                "API_TOKEN": "token-123",
                "prequal/app": '{"DB_PASSWORD": "pw", "SECRET_KEY": "sk"}',
            }
        ),
    )
    mgr = sm.SecretsManager(enabled=True)
    populated = mgr.hydrate_environment(["API_TOKEN", "prequal/app"])
    assert set(populated) == {"API_TOKEN", "DB_PASSWORD", "SECRET_KEY"}
    assert os.environ["API_TOKEN"] == "token-123"
    assert os.environ["DB_PASSWORD"] == "pw"


def test_hydrate_never_overwrites_existing(monkeypatch) -> None:
    monkeypatch.setenv("DB_PASSWORD", "already-set")
    _install_boto3(monkeypatch, _FakeSMClient({"prequal/app": '{"DB_PASSWORD": "new"}'}))
    mgr = sm.SecretsManager(enabled=True)
    assert mgr.hydrate_environment(["prequal/app"]) == []
    assert os.environ["DB_PASSWORD"] == "already-set"


def test_hydrate_reads_secret_names_from_env(monkeypatch) -> None:
    monkeypatch.setenv(sm.ENVIRONMENT_SECRETS_ENV, "A, B ,")
    monkeypatch.delenv("A", raising=False)
    monkeypatch.delenv("B", raising=False)
    _install_boto3(monkeypatch, _FakeSMClient({"A": "va", "B": "vb"}))
    mgr = sm.SecretsManager(enabled=True)
    assert set(mgr.hydrate_environment()) == {"A", "B"}


def test_module_level_hydrate_delegates(monkeypatch) -> None:
    monkeypatch.setattr(sm.secrets_manager, "_enabled", True)
    monkeypatch.setattr(sm.secrets_manager, "_load_payload", lambda name: {"value": "v"})
    monkeypatch.delenv("MODSECRET", raising=False)
    assert sm.hydrate_environment(["MODSECRET"]) == ["MODSECRET"]
