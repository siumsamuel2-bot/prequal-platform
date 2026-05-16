"""Run Alembic migrations and optional seed for local development.

Usage:
    python scripts/run_migrations.py [--seed]
"""
import argparse
import os
import sys

PROJECT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, PROJECT_DIR)

from sqlalchemy import create_engine
from alembic.config import Config
from alembic import command

def run_migrations(seed: bool = False):
    alembic_cfg = Config(os.path.join(PROJECT_DIR, "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    print("Alembic migrations applied successfully.")

    if seed:
        from scripts.seed_data import seed_database
        result = seed_database()
        print("Seed Summary:")
        for tbl in result["tables"]:
            print(f"  {tbl}: {result['counts'][tbl]} records")


def main():
    parser = argparse.ArgumentParser(description="Run Alembic migrations for Prequal")
    parser.add_argument("--seed", action="store_true", help="Also run seed data after migrations")
    args = parser.parse_args()
    run_migrations(seed=args.seed)


if __name__ == "__main__":
    main()
