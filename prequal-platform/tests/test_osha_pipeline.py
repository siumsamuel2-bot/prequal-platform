import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.osha_client import OSHAClient
from scripts.etl_osha import _extract_violation_record, _extract_inspection_record


# ---------------------------------------------------------------------------
# OSHA Client Tests
# ---------------------------------------------------------------------------

class TestOSHAClientUnit:
    @pytest.mark.asyncio
    async def test_search_cases_uses_pagination(self):
        client = OSHAClient()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = '{"results": [{"id": 1}], "count": 1}'
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

        data = await client.search_cases(search="acme", page=1, page_size=10)
        assert isinstance(data, dict)
        assert "results" in data
        await client.close()

    @pytest.mark.asyncio
    async def test_paginate_cases_honors_max_pages(self):
        client = OSHAClient()
        total_calls = 0

        async def mock_search(*, page, **kwargs):
            nonlocal total_calls
            total_calls += 1
            if page > 1:
                return {"results": [], "count": 10}
            return {"results": [{"id": page}], "count": 10}

        client.search_cases = mock_search
        results = await client.paginate_cases(search="acme", max_pages=1)
        assert len(results) == 1
        assert results[0]["id"] == 1
        await client.close()


class TestExtractViolationRecord:
    def test_simple_case(self):
        case = {
            "id": 123,
            "case_number": "ABC-456",
            "allegation": "Fall hazard",
            "type": "osha",
            "date_opened": "2025-01-15",
            "date_closed": "2025-03-10",
            "status": "closed",
            "inspection_number": "INS-789",
        }
        record = _extract_violation_record(case)
        assert record["violation_code"] == "ABC-456"
        assert record["description"] == "Fall hazard"
        assert record["status"] == "resolved"
        assert record["is_osha_violation"] is True
        assert record["issued_date"] == date(2025, 1, 15)
        assert record["resolution_date"] == date(2025, 3, 10)

    def test_open_case(self):
        case = {
            "id": 124,
            "case_number": "ABC-457",
            "summary": "Missing guardrails",
            "date_opened": "2026-05-01",
            "status": "open",
        }
        record = _extract_violation_record(case)
        assert record["status"] == "open"
        assert record["resolution_date"] is None


class TestExtractInspectionRecord:
    def test_basic_mapping(self):
        case = {
            "id": 999,
            "inspection_number": "INS-2025-001",
            "date_opened": "2025-06-01",
            "city": "Columbus",
            "state": "OH",
            "address": "123 Main St",
            "naics": "236220",
        }
        record = _extract_inspection_record(case)
        assert record["inspection_number"] == "INS-2025-001"
        assert record["site_city"] == "Columbus"
        assert record["naics_code"] == "236220"
        assert record["inspection_date"] == date(2025, 6, 1)
