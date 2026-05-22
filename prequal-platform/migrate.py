#!/usr/bin/env python3
"""
Database Migration Script for CI/CD Pipeline

Usage:
    python migrate.py upgrade      # Upgrade to latest
    python migrate.py downgrade    # Downgrade one version
    python migrate.py current      # Show current version
    python migrate.py history      # Show migration history
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_alembic_config():
    """Get Alembic configuration."""
    alembic_ini = Path(__file__).parent / "alembic.ini"
    return Config(str(alembic_ini))


def migrate_upgrade():
    """Upgrade database to latest version."""
    logger.info("Starting database migration (upgrade)...")
    try:
        alembic_cfg = get_alembic_config()
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migration completed successfully")
        return True
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def migrate_downgrade():
    """Downgrade database by one version."""
    logger.info("Starting database migration (downgrade)...")
    try:
        alembic_cfg = get_alembic_config()
        command.downgrade(alembic_cfg, "-1")
        logger.info("Database downgrade completed successfully")
        return True
    except Exception as e:
        logger.error(f"Migration downgrade failed: {e}")
        return False


def migrate_current():
    """Show current database version."""
    try:
        alembic_cfg = get_alembic_config()
        command.current(alembic_cfg)
        return True
    except Exception as e:
        logger.error(f"Failed to get current version: {e}")
        return False


def migrate_history():
    """Show migration history."""
    try:
        alembic_cfg = get_alembic_config()
        script = ScriptDirectory.from_config(alembic_cfg)
        for revision in script.walk_revisions():
            print(f"{revision.revision} -> {revision.docstring or '(no message)'}")
        return True
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    action = sys.argv[1]
    
    actions = {
        "upgrade": migrate_upgrade,
        "downgrade": migrate_downgrade,
        "current": migrate_current,
        "history": migrate_history,
    }
    
    if action in actions:
        success = actions[action]()
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown action: {action}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
