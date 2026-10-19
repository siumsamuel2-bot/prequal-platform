"""Coverage for app/services/state_compliance_service.py (MID-676).

Covers the active-source lookup, the single- and cross-state lookups, the
pipeline delegation wrappers, and the multi-state orchestrator (including its
per-state failure isolation). The external compliance pipeline is stubbed so no
network or live ETL runs.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models.compliance import StateCredentialRecord
from app.models.state_compliance import StateComplianceSource
from app.services import state_compliance_service as scs

CODES = ["QA", "QB", "QC", "ZZ"]


@pytest_asyncio.fixture(autouse=True)
async def _clean_state_tables(db_engine):
    async def _purge():
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(StateCredentialRecord).where(
                    StateCredentialRecord.state_code.in_(CODES)
                )
            )
            await session.execute(
                delete(StateComplianceSource).where(
                    StateComplianceSource.state_code.in_(CODES)
                )
            )
            await session.commit()

    await _purge()
    yield
    await _purge()


def _source(code: str, *, active: bool = True, priority: int = 0) -> StateComplianceSource:
    return StateComplianceSource(
        state_code=code,
        state_name=f"State {code}",
        api_url=f"https://{code.lower()}.example.test",
        is_active=active,
        priority=priority,
    )


def _record(code: str, number: str, name: str, ctype: str = "contractor_license"):
    return StateCredentialRecord(
        state_code=code,
        credential_number=number,
        credential_type=ctype,
        issuing_state=code,
        holder_name=name,
        status="active",
        expiration_date=date.today() + timedelta(days=30),
        external_source_url=f"https://{code.lower()}.example.test/{number}",
    )


@pytest.mark.asyncio
async def test_get_active_sources_orders_and_filters(db_session):
    db_session.add_all(
        [
            _source("QB", active=True, priority=2),
            _source("QA", active=True, priority=1),
            _source("QC", active=False, priority=0),
        ]
    )
    await db_session.commit()

    sources = await scs.get_active_sources(db_session)

    # Other modules may seed their own active sources, so scope to ours while
    # still asserting priority ordering and the inactive-row filter.
    mine = [s.state_code for s in sources if s.state_code in {"QA", "QB", "QC"}]
    assert mine == ["QA", "QB"]
    assert all(s.is_active for s in sources)


@pytest.mark.asyncio
async def test_lookup_contractor_unconfigured_state(db_session):
    result = await scs.lookup_contractor_in_state("ZZ", "Acme", db=db_session)
    assert result["status"] == "not_found"
    assert "ZZ" in result["message"]


@pytest.mark.asyncio
async def test_lookup_contractor_matches_by_name_and_number(db_session):
    db_session.add(_source("QA"))
    db_session.add_all(
        [
            _record("QA", "QA-100", "Acme Builders", ctype="contractor_license"),
            _record("QA", "QA-200", "Other Co", ctype="safety"),
        ]
    )
    await db_session.commit()

    by_name = await scs.lookup_contractor_in_state("qa", "Acme", db=db_session)
    assert by_name["status"] == "success"
    assert by_name["records_found"] == 1
    assert by_name["results"][0]["credential_number"] == "QA-100"

    by_number = await scs.lookup_contractor_in_state("QA", "QA-200", db=db_session)
    assert by_number["records_found"] == 1
    assert by_number["results"][0]["holder_name"] == "Other Co"

    filtered = await scs.lookup_contractor_in_state(
        "QA", "QA", db=db_session, credential_type="safety"
    )
    assert filtered["records_found"] == 1
    assert filtered["results"][0]["credential_type"] == "safety"


@pytest.mark.asyncio
async def test_sync_state_credentials_delegates(db_session, monkeypatch):
    run_id = uuid.uuid4()

    async def _fake_sync(**kwargs):
        assert kwargs["db"] is db_session
        assert kwargs["state_code"] == "QA"
        assert kwargs["triggered_by"] == "manual"
        return SimpleNamespace(
            id=run_id,
            status="completed",
            records_extracted=10,
            records_inserted=8,
            records_updated=1,
            records_failed=1,
            records_matched=7,
        )

    async def _fake_health(_db):
        return {"healthy": True}

    monkeypatch.setattr(scs, "run_state_credential_sync", _fake_sync)
    monkeypatch.setattr(scs, "validate_pipeline_health", _fake_health)

    result = await scs.sync_state_credentials(
        "QA", db=db_session, triggered_by="manual", max_results=5
    )

    assert result == {
        "status": "completed",
        "state": "QA",
        "run_id": str(run_id),
        "extracted": 10,
        "inserted": 8,
        "updated": 1,
        "failed": 1,
        "matched": 7,
        "validation": {"healthy": True},
    }


@pytest.mark.asyncio
async def test_check_contractor_across_states(db_session):
    db_session.add_all([_source("QA", priority=1), _source("QB", priority=2)])
    db_session.add_all(
        [
            _record("QA", "QA-300", "Acme Builders"),
            _record("QB", "QB-300", "Acme Builders"),
        ]
    )
    await db_session.commit()

    result = await scs.check_contractor_across_states("Acme", db=db_session)

    assert result["company_name"] == "Acme"
    assert result["states_checked"] == len(result["results"])
    assert result["results"]["QA"]["status"] == "success"
    assert result["results"]["QB"]["status"] == "success"
    assert result["results"]["QA"]["records_found"] == 1


@pytest.mark.asyncio
async def test_full_state_pipeline_sync_no_states():
    result = await scs.full_state_pipeline_sync(state_codes=[])
    assert result == {"status": "no_states_configured", "results": {}}


@pytest.mark.asyncio
async def test_full_state_pipeline_sync_isolates_failures(monkeypatch):
    class _FakeDB:
        closed = False

        async def close(self):
            self.closed = True

    fake_db = _FakeDB()
    monkeypatch.setattr(scs, "AsyncSessionLocal", lambda: fake_db)

    async def _fake_sync(state_code, *, db=None, triggered_by="schedule"):
        if state_code == "QB":
            raise RuntimeError("board api down")
        return {"status": "completed", "state": state_code}

    monkeypatch.setattr(scs, "sync_state_credentials", _fake_sync)

    result = await scs.full_state_pipeline_sync(
        state_codes=["QA", "QB"], triggered_by="manual"
    )

    assert result["results"]["QA"]["status"] == "completed"
    assert result["results"]["QB"] == {"status": "failed", "error": "board api down"}
    assert "started_at" in result and "completed_at" in result
    assert fake_db.closed is True


@pytest.mark.asyncio
async def test_full_state_pipeline_sync_uses_env_codes(monkeypatch):
    class _FakeDB:
        async def close(self):
            return None

    monkeypatch.setattr(scs, "AsyncSessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(scs, "SUPPORTED_STATE_CODES", {"QA": "https://qa"})

    seen = []

    async def _fake_sync(state_code, *, db=None, triggered_by="schedule"):
        seen.append(state_code)
        return {"status": "completed", "state": state_code}

    monkeypatch.setattr(scs, "sync_state_credentials", _fake_sync)

    result = await scs.full_state_pipeline_sync()

    assert seen == ["QA"]
    assert result["results"]["QA"]["status"] == "completed"
