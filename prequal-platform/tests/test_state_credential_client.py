import pytest
from datetime import date
from unittest.mock import AsyncMock

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.state_credential_client import StateCredentialClient


class TestStateCredentialClientUnit:
    @pytest.mark.asyncio
    async def test_fetch_credentials_returns_empty_when_no_url(self):
        client = StateCredentialClient(state_code="CA")
        result = await client.fetch_credentials(query="test")
        assert result["results"] == []
        assert result["count"] == 0
        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_credentials_uses_params(self):
        client = StateCredentialClient(state_code="TX", base_url="https://api.example.com")
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"results": [{"id": 1}], "count": 1}

        class FakeCtx:
            def __init__(self, response):
                self.response = response
            async def __aenter__(self):
                return self.response
            async def __aexit__(self, exc_type, exc, tb):
                return None

        class FakeSession:
            def __init__(self, response):
                self.response = response
                self.closed = False
            def get(self, *args, **kwargs):
                return FakeCtx(self.response)
            async def close(self):
                pass

        client._session = FakeSession(mock_response)

        result = await client.fetch_credentials(query="electrician", active_only=True, page=1, page_size=25)
        assert isinstance(result, dict)
        assert "results" in result
        await client.close()

    @pytest.mark.asyncio
    async def test_paginate_credentials_honors_max_pages(self):
        client = StateCredentialClient(state_code="FL", base_url="https://api.example.com")
        total_calls = 0

        async def mock_fetch_credentials(*, page, **kwargs):
            nonlocal total_calls
            total_calls += 1
            if page > 1:
                return {"results": [], "count": 10}
            return {"results": [{"id": page}], "count": 10}

        client.fetch_credentials = mock_fetch_credentials
        results = await client.paginate_credentials(query="contractor", max_pages=1)
        assert len(results) == 1
        assert results[0]["id"] == 1
        await client.close()

    @pytest.mark.asyncio
    async def test_paginate_credentials_stops_on_empty_results(self):
        client = StateCredentialClient(state_code="NY", base_url="https://api.example.com")

        async def mock_fetch_credentials(*, page, **kwargs):
            return {"results": [], "count": 0}

        client.fetch_credentials = mock_fetch_credentials
        results = await client.paginate_credentials(query="builder")
        assert results == []
        await client.close()


class TestStateCredentialClientEnvVars:
    def test_state_code_uppercased(self):
        client = StateCredentialClient(state_code="ca")
        assert client.state_code == "CA"

    def test_base_url_from_env(self):
        os.environ["STATE_API_URL_CA"] = "https://ca.licensing.board/api"
        client = StateCredentialClient(state_code="CA")
        assert client.base_url == "https://ca.licensing.board/api"
        del os.environ["STATE_API_URL_CA"]

    def test_api_key_from_env(self):
        os.environ["STATE_API_URL_CA"] = "https://ca.licensing.board/api"
        os.environ["STATE_API_KEY_CA"] = "secret-key-123"
        client = StateCredentialClient(state_code="CA")
        assert client.api_key == "secret-key-123"
        del os.environ["STATE_API_URL_CA"]
        del os.environ["STATE_API_KEY_CA"]

    def test_no_api_key_when_not_set(self):
        os.environ["STATE_API_URL_TX"] = "https://tx.licensing.board/api"
        client = StateCredentialClient(state_code="TX")
        assert client.api_key is None
        del os.environ["STATE_API_URL_TX"]


class TestStateCredentialClientContextManager:
    @pytest.mark.asyncio
    async def test_context_manager_closes_session(self):
        client = StateCredentialClient(state_code="AZ", base_url="https://az.gov/api")
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"results": [], "count": 0}

        class FakeCtx:
            def __init__(self, response):
                self.response = response
            async def __aenter__(self):
                return self.response
            async def __aexit__(self, exc_type, exc, tb):
                return None

        class FakeSession:
            def __init__(self, response):
                self.response = response
                self.closed = False
            def get(self, *args, **kwargs):
                return FakeCtx(self.response)
            async def close(self):
                self.closed = True

        client._session = FakeSession(mock_response)
        async with client:
            pass
        assert client._session.closed is True