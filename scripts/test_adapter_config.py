#!/usr/bin/env python3
"""Regression test: ensure Security Engineer adapter config does not regress.

Validates that the opencode_local adapter is configured with sufficient
grace and timeout values to prevent silent-run timeouts.
"""

import os
import requests
import sys

API_URL = os.environ.get("PAPERCLIP_API_URL")
API_KEY = os.environ.get("PAPERCLIP_API_KEY")
AGENT_ID = os.environ.get("PAPERCLIP_AGENT_ID", "6ea10cd9-4dfe-4a83-821c-048581805d4d")


def test_adapter_config():
    if not API_URL or not API_KEY:
        print("ERROR: PAPERCLIP_API_URL and PAPERCLIP_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    url = f"{API_URL}/api/agents/{AGENT_ID}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"ERROR: Failed to fetch agent config: {exc}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    adapter_config = data.get("adapterConfig", {})

    grace = adapter_config.get("graceSec")
    timeout = adapter_config.get("timeoutSec")

    errors = []
    if grace is None:
        errors.append("graceSec missing from adapterConfig")
    elif grace < 120:
        errors.append(f"graceSec too low: {grace} (expected >= 120)")

    if timeout is None:
        errors.append("timeoutSec missing from adapterConfig")
    elif timeout < 600:
        errors.append(f"timeoutSec too low: {timeout} (expected >= 600)")

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        sys.exit(1)

    print(f"PASS: Adapter config OK (graceSec={grace}, timeoutSec={timeout})")
    sys.exit(0)


if __name__ == "__main__":
    test_adapter_config()
