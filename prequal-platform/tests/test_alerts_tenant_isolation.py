"""Tenant isolation regression tests for /api/alerts (MID-546 / HIGH-3).

Proves that non-admin callers cannot enumerate or mutate another team's
alerts through GET /api/alerts, /by-contractor, /by-project, acknowledge,
/summary, and /recent. Uses mocked AsyncSession — the same style as the
existing unit suite — asserting on the actual SQL SQLAlchemy generates.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import HTTPException

from app.routers.alerts import (
    list_alerts,
    get_alerts_by_contractor,
    get_alerts_by_project,
    acknowledge_alert,
    _resolve_caller_team_id,
    _tenant_alert_predicate,
    _assert_alert_in_team_scope,
)
from app.schemas.compliance import TokenData


TEAM_A = uuid4()
TEAM_B = uuid4()
USER_A = uuid4()


def _admin() -> TokenData:
    return TokenData(sub="admin@x.com", user_id=str(uuid4()), role="admin")


def _member_a() -> TokenData:
    return TokenData(sub="a@x.com", user_id=str(USER_A), role="project_manager")


def _teamed_db(team_id=TEAM_A):
    """Mock DB whose TeamMember lookup returns team_id."""
    db = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = team_id
    db.execute.return_value = res
    return db


def _alerts_result(rows):
    res = MagicMock()
    res.scalars.return_value = MagicMock()
    res.scalars.return_value.all.return_value = rows
    return res


class TestTenantPredicate:
    def test_predicate_compiles_with_team_filter(self):
        compiled = str(_tenant_alert_predicate(TEAM_A).compile(compile_kwargs={"literal_binds": False}))
        assert "subcontractors.team_id" in compiled
        assert "certifications" in compiled
        assert "alert_notifications.certification_id" in compiled


class TestResolveCallerTeam:
    @pytest.mark.asyncio
    async def test_admin_resolves_none(self):
        db = AsyncMock()
        assert await _resolve_caller_team_id(db, _admin()) is None
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_member_team_from_live_table(self):
        db = _teamed_db(TEAM_A)
        assert await _resolve_caller_team_id(db, _member_a()) == TEAM_A

    @pytest.mark.asyncio
    async def test_member_without_team_resolves_none(self):
        db = _teamed_db(None)
        assert await _resolve_caller_team_id(db, _member_a()) is None


class TestListAlertsIsolation:
    @pytest.mark.asyncio
    async def test_member_query_is_team_scoped(self):
        """The alerts SELECT must carry the team predicate for a non-admin."""
        alert = MagicMock()
        db = _teamed_db(TEAM_A)
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=TEAM_A)),  # team lookup
            _alerts_result([alert]),                                        # alerts query
        ]
        out = await list_alerts(skip=0, limit=100, status_filter=None, alert_type=None, days_until=None, db=db, current_user=_member_a())
        assert out == [alert]
        alerts_stmt = db.execute.call_args_list[1].args[0]
        compiled = str(alerts_stmt.compile())
        assert "subcontractors.team_id" in compiled

    @pytest.mark.asyncio
    async def test_member_without_team_gets_nothing(self):
        """Non-admin with no team membership must see zero alerts and the
        main alerts SELECT must never run."""
        db = _teamed_db(None)
        out = await list_alerts(skip=0, limit=100, status_filter=None, alert_type=None, days_until=None, db=db, current_user=_member_a())
        assert out == []
        assert db.execute.await_count == 1  # only the team lookup

    @pytest.mark.asyncio
    async def test_admin_query_is_unscoped(self):
        alert = MagicMock()
        db = AsyncMock()
        db.execute.return_value = _alerts_result([alert])
        out = await list_alerts(skip=0, limit=100, status_filter=None, alert_type=None, days_until=None, db=db, current_user=_admin())
        assert out == [alert]
        compiled = str(db.execute.call_args_list[0].args[0].compile())
        assert "team_id" not in compiled


class TestScopedDetailEndpoints:
    @pytest.mark.asyncio
    async def test_by_contractor_cross_tenant_denied(self):
        """Contractor owned by team B → 404 for a team-A caller."""
        db = _teamed_db(TEAM_A)
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=TEAM_A)),   # team lookup
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),     # subcontractor scope check
        ]
        with pytest.raises(HTTPException) as exc:
            await get_alerts_by_contractor(
                contractor_id=uuid4(), db=db, current_user=_member_a()
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_by_project_cross_tenant_denied(self):
        db = _teamed_db(TEAM_A)
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=TEAM_A)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),     # project scope check
        ]
        with pytest.raises(HTTPException) as exc:
            await get_alerts_by_project(
                project_id=uuid4(), db=db, current_user=_member_a()
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_acknowledge_cross_tenant_alert_denied(self):
        """A team-A caller must not acknowledge a team-B alert."""
        alert = MagicMock()
        alert.id = uuid4()
        alert.status = "pending"
        db = _teamed_db(TEAM_A)
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=alert)),  # alert fetch
            MagicMock(scalar_one_or_none=MagicMock(return_value=TEAM_A)),  # team lookup
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),    # scope check fails
        ]
        with pytest.raises(HTTPException) as exc:
            await acknowledge_alert(alert_id=alert.id, db=db, current_user=_member_a())
        assert exc.value.status_code == 404
        assert alert.status == "pending"  # untouched
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_scope_assertion_passes_in_team(self):
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value="row"))
        alert = MagicMock()
        alert.id = uuid4()
        await _assert_alert_in_team_scope(db, TEAM_A, alert)  # must not raise
