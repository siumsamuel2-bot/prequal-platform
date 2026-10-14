"""Runtime environment helpers.

Centralises how the API decides whether it is running in a developer
environment (interactive docs enabled, unauthenticated observability
endpoints allowed) versus a shared deployment (staging/production, where
the public information surface is reduced — MID-690).

The ``ENVIRONMENT`` variable is the deployment-wide convention:
Render staging sets ``ENVIRONMENT=staging`` (render.yaml), Fly sets
``ENVIRONMENT=production`` (fly.toml). Anything unrecognised or unset is
treated as development so local ``uvicorn api.main:app`` runs keep docs.
"""

from __future__ import annotations

import os

#: Environment names in which interactive docs and unauthenticated
#: observability endpoints are permitted.
DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing"})


def current_environment() -> str:
    """Return the normalized (lowercase, stripped) ENVIRONMENT value."""
    return os.getenv("ENVIRONMENT", "development").strip().lower()


def is_dev_environment() -> bool:
    """True when running locally (docs and open observability allowed)."""
    return current_environment() in DEV_ENVIRONMENTS
