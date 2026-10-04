#!/usr/bin/env python3
"""Standalone hardcoded-secret scanner (MID-594).

A dependency-free backstop to the gitleaks CI job so secrets can also be
checked locally and in environments where the gitleaks binary is unavailable.
It scans files tracked by git (or an explicit path) for high-signal secret
patterns and fails with a non-zero exit code when anything suspicious is found.

Usage:
    python scripts/scan_secrets.py [path ...]
    python scripts/scan_secrets.py --staged      # only git-staged files

Exit codes:
    0 - no findings
    1 - potential secret(s) found
    2 - scanner error
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Iterable, List, Tuple

# High-signal patterns only, to keep the false-positive rate near zero.
PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("aws-access-key", re.compile(r"(?<![A-Z0-9])(AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA)[A-Z0-9]{16}")),
    ("stripe-live", re.compile(r"sk_live_[0-9a-zA-Z]{24,}")),
    ("sendgrid", re.compile(r"SG\.[0-9A-Za-z_-]{22}\.[0-9A-Za-z_-]{43}")),
    ("github-token", re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}")),
    ("slack-token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|ENCRYPTED) PRIVATE KEY-----")),
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("postgres-url", re.compile(r"postgres(?:ql)?://[^\s:@/]+:[^\s:@/]{6,}@")),
]

# Substrings that mark a match as a placeholder / test value rather than a leak.
ALLOW_MARKERS = (
    "example",
    "placeholder",
    "replace_with",
    "replace-with",
    "your_",
    "your-",
    "changeme",
    "change_me",
    "dummy",
    "fake",
    "xxx",
    "test-",
    "test_",
    "<",
    "${",
    "dbname",
    "user:password",
    "host:port",
)

SKIP_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
}

SKIP_SUFFIXES = (
    ".lock",
    ".db",
    ".db-journal",
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".pdf",
    ".zip",
    ".min.js",
    ".map",
)


def _git(*args: str) -> List[str]:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _is_skipped(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    parts = lowered.split("/")
    if any(part in SKIP_DIRS for part in parts):
        return True
    return lowered.endswith(SKIP_SUFFIXES)


def _has_allow_marker(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in ALLOW_MARKERS)


# Connection strings pointing at a local/dev database are not production
# secrets and would otherwise drown out real findings.
_LOCAL_DB_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0", "@db:", "@postgres:", "host.docker.internal")


def _scan_line(line: str) -> List[str]:
    findings = []
    if _has_allow_marker(line):
        return findings
    lowered = line.lower()
    for name, pattern in PATTERNS:
        if not pattern.search(line):
            continue
        if name == "postgres-url":
            if any(marker in lowered for marker in _LOCAL_DB_MARKERS):
                continue
            if "{" in line or "${" in line or "%(" in line:
                continue
        findings.append(name)
    return findings


def scan_paths(paths: Iterable[str]) -> List[Tuple[str, int, str]]:
    findings: List[Tuple[str, int, str]] = []
    for path in paths:
        if _is_skipped(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                for number, line in enumerate(handle, start=1):
                    for rule in _scan_line(line):
                        findings.append((path, number, rule))
        except (OSError, IsADirectoryError):
            continue
    return findings


def _collect_paths(explicit: List[str], staged: bool) -> List[str]:
    if staged:
        return _git("diff", "--cached", "--name-only", "--diff-filter=ACM")
    if explicit:
        return explicit
    return _git("ls-files")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for hardcoded secrets.")
    parser.add_argument("paths", nargs="*", help="Files or directories to scan.")
    parser.add_argument("--staged", action="store_true", help="Scan only git-staged files.")
    args = parser.parse_args()

    try:
        paths = _collect_paths(args.paths, args.staged)
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"error: could not enumerate files: {exc}", file=sys.stderr)
        return 2

    findings = scan_paths(paths)
    if findings:
        print("Potential hardcoded secrets detected:")
        for path, number, rule in findings:
            print(f"  {path}:{number}  [{rule}]")
        print(f"\n{len(findings)} finding(s). Remove the secret and rotate it.")
        return 1

    print(f"Secret scan clean ({len(paths)} file(s) checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
