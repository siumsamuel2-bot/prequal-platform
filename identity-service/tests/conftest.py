"""
Test configuration for identity-service.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set test environment variables
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["POSTGRES_PASSWORD"] = "test"