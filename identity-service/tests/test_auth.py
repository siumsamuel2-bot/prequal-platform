"""
Tests for identity-service authentication endpoints.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app
from app.models.models import User, UserSession, Organization
from app.services.security import hash_password, verify_password, generate_session_token, generate_rotation_token


class TestSecurityUtilities:
    """Test security utility functions."""

    def test_hash_password_produces_hash(self):
        password = "testpass123"
        hashed = hash_password(password)
        assert hashed is not None
        assert len(hashed) > 0
        assert "$" in hashed  # pbkdf2 format

    def test_verify_password_correct(self):
        password = "correcthorse"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        password = "correcthorse"
        wrong_password = "wrongpassword"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False

    def test_generate_session_token_length(self):
        token = generate_session_token()
        assert len(token) >= 32

    def test_generate_rotation_token_length(self):
        token = generate_rotation_token()
        assert len(token) >= 20

    def test_unique_tokens(self):
        tokens = {generate_session_token() for _ in range(100)}
        assert len(tokens) == 100


class TestAuthEndpoints:
    """Test authentication endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)

    @pytest.fixture
    def sample_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.hashed_password = hash_password("testpass123")
        user.full_name = "Test User"
        user.organization_id = None
        user.role = "user"
        user.is_active = True
        user.created_at = datetime.utcnow()
        user.last_password_change = None
        return user

    @pytest.fixture
    def sample_org(self):
        org = MagicMock(spec=Organization)
        org.id = 1
        org.name = "Test Org"
        org.created_at = datetime.utcnow()
        org.updated_at = datetime.utcnow()
        return org

    def test_login_success(self, client, sample_user):
        with patch("app.api.endpoints.auth.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = sample_user
            mock_get_db.return_value = iter([mock_db])

            with patch("app.api.endpoints.auth.store_session_in_redis", new_callable=AsyncMock):
                response = client.post(
                    "/api/v1/auth/login",
                    json={"email": "test@example.com", "password": "testpass123"}
                )
                assert response.status_code == 200
                data = response.json()
                assert "token" in data
                assert "rotation_token" in data
                assert "expires_at" in data

    def test_login_invalid_credentials(self, client):
        with patch("app.api.endpoints.auth.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = iter([mock_db])

            response = client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"}
            )
            assert response.status_code == 401

    def test_login_disabled_user(self, client, sample_user):
        sample_user.is_active = False
        with patch("app.api.endpoints.auth.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = sample_user
            mock_get_db.return_value = iter([mock_db])

            response = client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpass123"}
            )
            assert response.status_code == 403

    def test_logout_success(self, client):
        with patch("app.api.endpoints.auth.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_session = MagicMock()
            mock_session.is_valid = True
            mock_db.query.return_value.filter.return_value.first.return_value = mock_session
            mock_get_db.return_value = iter([mock_db])

            with patch("app.api.endpoints.auth.delete_session_from_redis", new_callable=AsyncMock):
                response = client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": "Bearer valid-token"}
                )
                assert response.status_code == 200
                assert response.json()["message"] == "Logged out successfully"
                assert mock_session.is_valid is False

    def test_logout_missing_token(self, client):
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 401

    def test_logout_all_success(self, client):
        with patch("app.api.endpoints.auth.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_session = MagicMock()
            mock_session.user_id = 1
            mock_db.query.return_value.filter.return_value.first.return_value = mock_session
            mock_get_db.return_value = iter([mock_db])

            with patch("app.api.endpoints.auth.delete_all_user_sessions_from_redis", new_callable=AsyncMock):
                response = client.post(
                    "/api/v1/auth/logout-all",
                    headers={"Authorization": "Bearer valid-token"}
                )
                assert response.status_code == 200
                assert response.json()["message"] == "All sessions invalidated"

    def test_session_rotation_success(self, client):
        with patch("app.api.endpoints.auth.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_session = MagicMock()
            mock_session.user_id = 1
            mock_session.rotation_token = "valid-rotation-token"
            mock_session.expires_at = datetime.utcnow() + timedelta(hours=1)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_session
            mock_get_db.return_value = iter([mock_db])

            with patch("app.api.endpoints.auth.delete_session_from_redis", new_callable=AsyncMock):
                with patch("app.api.endpoints.auth.store_session_in_redis", new_callable=AsyncMock):
                    response = client.post(
                        "/api/v1/auth/session/rotate",
                        json={
                            "current_token": "valid-token",
                            "rotation_token": "valid-rotation-token"
                        }
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert "token" in data
                    assert "rotation_token" in data
                    assert "expires_at" in data

    def test_session_rotation_invalid_rotation_token(self, client):
        with patch("app.api.endpoints.auth.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_session = MagicMock()
            mock_session.user_id = 1
            mock_session.rotation_token = "different-rotation-token"
            mock_session.expires_at = datetime.utcnow() + timedelta(hours=1)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_session
            mock_get_db.return_value = iter([mock_db])

            response = client.post(
                "/api/v1/auth/session/rotate",
                json={
                    "current_token": "valid-token",
                    "rotation_token": "invalid-rotation-token"
                }
            )
            assert response.status_code == 401


class TestUserEndpoints:
    """Test user management endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_create_user_success(self, client):
        with patch("app.api.endpoints.users.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_org = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_org
            mock_get_db.return_value = iter([mock_db])

            response = client.post(
                "/api/v1/users/",
                json={
                    "email": "newuser@example.com",
                    "password": "password123",
                    "full_name": "New User",
                    "role": "user"
                }
            )
            assert response.status_code == 201
            data = response.json()
            assert data["email"] == "newuser@example.com"
            assert data["full_name"] == "New User"

    def test_create_user_duplicate_email(self, client):
        with patch("app.api.endpoints.users.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_existing_user = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_existing_user
            mock_get_db.return_value = iter([mock_db])

            response = client.post(
                "/api/v1/users/",
                json={
                    "email": "existing@example.com",
                    "password": "password123"
                }
            )
            assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])