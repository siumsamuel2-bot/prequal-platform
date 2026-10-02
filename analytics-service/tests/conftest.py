"""
Test configuration for analytics-service.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ["DATABASE_URL"] = "sqlite:///./test_analytics.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["POSTGRES_PASSWORD"] = "test"
os.environ["SERVICE_API_KEY"] = "test-service-key"
os.environ["ENVIRONMENT"] = "test"
