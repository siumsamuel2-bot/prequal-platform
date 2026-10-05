"""
ETL Orchestrator for External Compliance Data Integration

Thin wrapper around the prequal-platform pipeline.
Maintains backward compatibility with existing run instructions.

Usage:
    python scripts/etl_external_compliance.py --job osha --state CA
    python scripts/etl_external_compliance.py --job state-creds --state TX
    python scripts/etl_external_compliance.py --job full-pipeline
"""

import sys
import os

# Delegate to the canonical implementation in prequal-platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prequal-platform"))

from app.services.external_compliance_pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
