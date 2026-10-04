"""Regression guard: the tracked tree must contain no hardcoded secrets (MID-594).

Runs the standalone scanner (``scripts/scan_secrets.py``) over the whole
repository. This complements the gitleaks CI job with a check that also works
locally and does not require the gitleaks binary.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "scripts" / "scan_secrets.py"


@pytest.mark.skipif(not SCANNER.exists(), reason="scanner script not present")
def test_repository_has_no_hardcoded_secrets():
    result = subprocess.run(
        [sys.executable, str(SCANNER)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Hardcoded secret scanner found issues:\n"
        f"{result.stdout}\n{result.stderr}"
    )
