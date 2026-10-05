"""
Daily Sync Runner for External Compliance Data

Runs the full external compliance pipeline on a schedule.
Intended to be invoked by a cron job or task scheduler (managed by DevOps).

Usage:
    python scripts/run_daily_sync.py [--state TX] [--state CA]

Environment:
    DATABASE_URL          PostgreSQL connection string
    OSHA_MAX_PAGES      Max pagination pages for OSHA (default 10)
    STATE_MAX_PAGES     Max pagination pages for state APIs (default 5)
    LOG_LEVEL           Logging level (default INFO)
"""

import sys
import os

# Delegate to the canonical implementation in prequal-platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prequal-platform"))

from app.services.external_compliance_pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
