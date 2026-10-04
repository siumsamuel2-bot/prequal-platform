"""Unit tests for the generic secrets-rotation Lambda (MID-594).

Run with the platform virtualenv (boto3 is already a dependency):

    python -m pytest terraform/secret_rotation/test_index.py -q
"""

import importlib.util
import json
import os

import pytest

# The Lambda module constructs a boto3 client at import time; give botocore a
# region so it can build the client outside of Lambda.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

_MODULE_PATH = os.path.join(os.path.dirname(__file__), "index.py")
_spec = importlib.util.spec_from_file_location("secret_rotation_index", _MODULE_PATH)
rotation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rotation)


class FakeSecretsManager:
    def __init__(self, current, rotation_keys="SECRET_KEY"):
        self.versions = {"AWSCURRENT": json.dumps(current)}
        self.metadata = {
            "RotationEnabled": True,
            "Tags": [{"Key": "RotationKeys", "Value": rotation_keys}],
        }
        self.stage_moves = []

    def describe_secret(self, SecretId):  # noqa: N803
        return self.metadata

    def get_secret_value(self, SecretId, VersionStage):  # noqa: N803
        if VersionStage not in self.versions:
            raise KeyError(VersionStage)
        return {"SecretString": self.versions[VersionStage]}

    def put_secret_value(self, SecretId, ClientRequestToken, SecretString):  # noqa: N803
        self.versions["AWSPENDING"] = SecretString

    def update_secret_version_stage(self, SecretId, VersionStage, MoveToVersionId, RemoveFromVersionId):  # noqa: N803
        self.stage_moves.append((VersionStage, MoveToVersionId, RemoveFromVersionId))
        self.versions["AWSCURRENT"] = self.versions.pop("AWSPENDING")


@pytest.fixture
def fake(monkeypatch):
    client = FakeSecretsManager({"SECRET_KEY": "old", "SMTP_HOST": "smtp.example.com"})
    monkeypatch.setattr(rotation, "secretsmanager", client)
    monkeypatch.delenv("ECS_CLUSTER", raising=False)
    monkeypatch.delenv("ECS_SERVICE", raising=False)
    return client


def test_full_rotation_cycle(fake):
    metadata = fake.describe_secret(SecretId="s")
    rotation.create_secret("s", "tok-1", metadata)

    pending = json.loads(fake.versions["AWSPENDING"])
    assert pending["SECRET_KEY"] != "old"
    assert pending["SMTP_HOST"] == "smtp.example.com"

    rotation.set_secret("s", "tok-1", metadata)
    rotation.test_secret("s", "tok-1", metadata)
    rotation.finish_secret("s", "tok-1", metadata)

    promoted = json.loads(fake.versions["AWSCURRENT"])
    assert promoted["SECRET_KEY"] == pending["SECRET_KEY"]
    assert fake.stage_moves == [("AWSCURRENT", "tok-1", None)]


def test_non_rotated_keys_are_preserved(fake):
    metadata = fake.describe_secret(SecretId="s")
    rotation.create_secret("s", "tok-1", metadata)
    pending = json.loads(fake.versions["AWSPENDING"])
    assert set(pending.keys()) == {"SECRET_KEY", "SMTP_HOST"}


def test_test_secret_rejects_unchanged_key(fake):
    fake.metadata["Tags"] = [{"Key": "RotationKeys", "Value": "SMTP_HOST"}]
    metadata = fake.describe_secret(SecretId="s")
    rotation.create_secret("s", "tok-1", metadata)
    # Force the pending value to equal current for the rotated key.
    current = json.loads(fake.versions["AWSCURRENT"])
    fake.versions["AWSPENDING"] = json.dumps(
        {"SECRET_KEY": current["SECRET_KEY"], "SMTP_HOST": current["SMTP_HOST"]}
    )
    with pytest.raises(ValueError):
        rotation.test_secret("s", "tok-1", metadata)


def test_empty_rotation_keys_is_noop_rotation(fake):
    fake.metadata["Tags"] = [{"Key": "RotationKeys", "Value": ""}]
    metadata = fake.describe_secret(SecretId="s")
    rotation.create_secret("s", "tok-1", metadata)
    pending = json.loads(fake.versions["AWSPENDING"])
    assert pending["SECRET_KEY"] == "old"


def test_lambda_handler_dispatches_steps(fake):
    event = {"SecretId": "s", "ClientRequestToken": "tok-1", "Step": "createSecret"}
    fake.metadata["VersionIdsToStages"] = {"tok-1": ["AWSPENDING"]}
    rotation.lambda_handler(event, None)
    assert "AWSPENDING" in fake.versions

    fake.metadata["VersionIdsToStages"] = {"tok-1": ["AWSPENDING"]}
    rotation.lambda_handler({**event, "Step": "finishSecret"}, None)
    assert fake.versions["AWSCURRENT"]
