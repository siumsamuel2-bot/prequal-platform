"""Generic AWS Secrets Manager rotation Lambda (MID-594).

Implements the standard four-step rotation contract for *self-contained*
secrets whose values the platform generates itself (for example the JWT
``SECRET_KEY`` signing value). Provider-managed credentials (Stripe, OSHA,
SMTP) cannot be rotated without calling the provider's API, so this function
only regenerates the keys named in the secret's ``RotationKeys`` tag; every
other key is preserved untouched.

Configuration
-------------
The secret tag ``RotationKeys`` (comma separated) lists the JSON keys that
should be regenerated on each rotation, e.g. ``SECRET_KEY``. If the tag is
empty the function performs a no-op rotation (useful for provider-managed
secrets so the 90-day schedule still records a rotation attempt).

Optional environment variables:
    ECS_CLUSTER   - ECS cluster name; when set with ECS_SERVICE a new
                    deployment is forced after rotation so consumers pick up
                    the new value.
    ECS_SERVICE   - ECS service name.
"""

import json
import logging
import os
import secrets
import string

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

secretsmanager = boto3.client("secretsmanager")

ROTATION_KEYS_TAG = "RotationKeys"
GENERATED_LENGTH = 48
_ALPHABET = string.ascii_letters + string.digits


def _get_tag(metadata, key, default=""):
    for tag in metadata.get("Tags", []) or []:
        if tag.get("Key") == key:
            return tag.get("Value", default) or default
    return default


def _rotation_keys(metadata):
    raw = _get_tag(metadata, ROTATION_KEYS_TAG, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _generate_value():
    return "".join(secrets.choice(_ALPHABET) for _ in range(GENERATED_LENGTH))


def _read_value(secret_id, stage):
    response = secretsmanager.get_secret_value(SecretId=secret_id, VersionStage=stage)
    payload = response.get("SecretString", "")
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {"value": payload}
    if isinstance(parsed, dict):
        return parsed
    return {"value": payload}


def create_secret(secret_id, token, metadata):
    """Create an AWSPENDING version with freshly generated values."""
    try:
        _read_value(secret_id, "AWSPENDING")
        logger.info("AWSPENDING already exists for %s; nothing to do", secret_id)
        return
    except Exception:
        pass

    current = _read_value(secret_id, "AWSCURRENT")
    pending = dict(current)
    keys = _rotation_keys(metadata)
    for key in keys:
        pending[key] = _generate_value()
    logger.info("Rotating %d key(s) for %s", len(keys), secret_id)

    secretsmanager.put_secret_value(
        SecretId=secret_id,
        ClientRequestToken=token,
        SecretString=json.dumps(pending),
    )


def set_secret(secret_id, token, metadata):
    """Push the new value to the backing dependency.

    Self-contained secrets have no external dependency to update, so this is a
    no-op. Provider-managed secrets must override this step before the
    ``RotationKeys`` tag is populated.
    """
    logger.info("setSecret: no external provider to update for %s", secret_id)


def test_secret(secret_id, token, metadata):
    """Verify the pending value is well formed before promoting it."""
    pending = _read_value(secret_id, "AWSPENDING")
    current = _read_value(secret_id, "AWSCURRENT")
    if set(current.keys()) - set(pending.keys()):
        raise ValueError("AWSPENDING is missing keys present in AWSCURRENT")
    for key in _rotation_keys(metadata):
        if pending.get(key) == current.get(key):
            raise ValueError(f"Key {key} was not rotated in AWSPENDING")
    logger.info("testSecret: AWSPENDING for %s looks valid", secret_id)


def _force_new_deployment():
    cluster = os.getenv("ECS_CLUSTER")
    service = os.getenv("ECS_SERVICE")
    if not cluster or not service:
        return
    try:
        boto3.client("ecs").update_service(
            cluster=cluster, service=service, force_new_deployment=True
        )
        logger.info("Forced new deployment for %s/%s", cluster, service)
    except Exception as exc:  # pragma: no cover - depends on AWS env
        logger.warning("Could not force ECS deployment: %s", exc)


def finish_secret(secret_id, token, metadata):
    """Promote AWSPENDING to AWSCURRENT."""
    current_version = None
    versions = metadata.get("VersionIdsToStages", {})
    for version_id, stages in versions.items():
        if "AWSCURRENT" in stages:
            if version_id == token:
                logger.info("AWSCURRENT already points at the pending version")
                return
            current_version = version_id
            break

    secretsmanager.update_secret_version_stage(
        SecretId=secret_id,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
        RemoveFromVersionId=current_version,
    )
    _force_new_deployment()
    logger.info("finishSecret: promoted %s to AWSCURRENT", secret_id)


def lambda_handler(event, context):
    secret_id = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]

    metadata = secretsmanager.describe_secret(SecretId=secret_id)
    if not metadata.get("RotationEnabled", False):
        raise ValueError(f"Secret {secret_id} is not enabled for rotation")

    versions = metadata.get("VersionIdsToStages", {})
    if token not in versions:
        raise ValueError("ClientRequestToken does not match a version of this secret")
    if "AWSCURRENT" in versions[token]:
        logger.info("Version %s is already AWSCURRENT; skipping", token)
        return
    if "AWSPENDING" not in versions[token]:
        raise ValueError("ClientRequestToken is not marked AWSPENDING")

    if step == "createSecret":
        create_secret(secret_id, token, metadata)
    elif step == "setSecret":
        set_secret(secret_id, token, metadata)
    elif step == "testSecret":
        test_secret(secret_id, token, metadata)
    elif step == "finishSecret":
        finish_secret(secret_id, token, metadata)
    else:
        raise ValueError(f"Unsupported rotation step: {step}")
