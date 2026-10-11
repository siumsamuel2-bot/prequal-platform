"""API coverage for app.routers.compliance (MID-676).

Exercises the top-level ``/api/certifications``, ``/api/violations`` and
``/api/projects`` routers plus the nested project/contractor views and the
read-only compliance status/dashboard endpoints through the real FastAPI app.

The caller is an admin token: ``require_caller_team_id`` intentionally returns
``None`` for admins (platform-wide/unscoped), which is the same convention the
existing subcontractor CRUD suite relies on, so no team rows are needed.

Rows are seeded with unique identifiers so the shared, session-scoped test
database is not polluted across runs. Assertions check real response contracts;
no endpoints are mocked away.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import Project, ProjectSubcontractor, Subcontractor
from app.routers.auth import get_current_user
from app.schemas.compliance import TokenData
from api.main import app as fastapi_app


def _admin() -> TokenData:
    return TokenData(
        sub="admin@example.com",
        user_id="00000000-0000-0000-0000-000000000001",
        role="admin",
    )


@pytest_asyncio.fixture(autouse=True)
async def _override_auth():
    fastapi_app.dependency_overrides[get_current_user] = _admin
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


async def _make_sub(db: AsyncSession, **kw) -> Subcontractor:
    sub = Subcontractor(
        company_name=kw.get("company_name", f"MID676 Sub {uuid.uuid4().hex[:8]}"),
        email=kw.get("email", f"mid676-{uuid.uuid4().hex[:10]}@example.com"),
        status=kw.get("status", "active"),
        city=kw.get("city"),
        state=kw.get("state"),
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def _make_project(db: AsyncSession, **kw) -> Project:
    proj = Project(
        project_name=kw.get("project_name", f"MID676 Project {uuid.uuid4().hex[:8]}"),
        client_name=kw.get("client_name"),
        status="planning",
    )
    db.add(proj)
    await db.commit()
    await db.refresh(proj)
    return proj


def _cert_payload(sub_id, **kw) -> dict:
    return {
        "subcontractor_id": str(sub_id),
        "certification_type": kw.get("certification_type", "OSHA 30"),
        "certification_number": kw.get("number", f"C-{uuid.uuid4().hex[:6]}"),
        "issuing_authority": "OSHA",
        "issue_date": "2025-01-15",
        "expiration_date": kw.get(
            "expiration_date", (date.today() + timedelta(days=400)).isoformat()
        ),
    }


def _violation_payload(sub_id, **kw) -> dict:
    return {
        "subcontractor_id": str(sub_id),
        "violation_type": kw.get("violation_type", "Safety"),
        "description": kw.get("description", "Fall protection violation"),
        "issued_date": kw.get("issued_date", date.today().isoformat()),
    }


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestProjectsAPI:
    async def test_create_and_get_project(self, async_client: AsyncClient) -> None:
        name = f"MID676 Created {uuid.uuid4().hex[:8]}"
        resp = await async_client.post(
            "/api/projects",
            json={
                "project_name": name,
                "project_number": f"P-{uuid.uuid4().hex[:8]}",
                "client_name": "Acme GC",
                "city": "Austin",
                "state": "TX",
                "budget": 125000.0,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["project_name"] == name
        assert body["client_name"] == "Acme GC"
        assert body["status"] == "planning"

        got = await async_client.get(f"/api/projects/{body['id']}")
        assert got.status_code == 200, got.text
        assert got.json()["id"] == body["id"]

    async def test_list_projects(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        await _make_project(db_session)
        resp = await async_client.get("/api/projects?limit=5")
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json(), list)

    async def test_get_project_404(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(
            "/api/projects/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_update_project(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        proj = await _make_project(db_session)
        resp = await async_client.patch(
            f"/api/projects/{proj.id}",
            json={"project_name": "Renamed", "status": "active"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["project_name"] == "Renamed"
        assert resp.json()["status"] == "active"

    async def test_update_project_404(self, async_client: AsyncClient) -> None:
        resp = await async_client.patch(
            "/api/projects/00000000-0000-0000-0000-000000000000",
            json={"project_name": "Nope"},
        )
        assert resp.status_code == 404

    async def test_delete_project(self, async_client: AsyncClient) -> None:
        created = await async_client.post(
            "/api/projects", json={"project_name": f"Del {uuid.uuid4().hex[:8]}"}
        )
        pid = created.json()["id"]
        resp = await async_client.delete(f"/api/projects/{pid}")
        assert resp.status_code == 204
        assert (await async_client.get(f"/api/projects/{pid}")).status_code == 404

    async def test_delete_project_404(self, async_client: AsyncClient) -> None:
        resp = await async_client.delete(
            "/api/projects/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestProjectSubcontractorsAPI:
    async def test_list_project_subcontractors(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        proj = await _make_project(db_session)
        sub = await _make_sub(db_session)
        db_session.add(
            ProjectSubcontractor(
                project_id=proj.id, subcontractor_id=sub.id, status="active"
            )
        )
        await db_session.commit()

        resp = await async_client.get(f"/api/projects/{proj.id}/subcontractors")
        assert resp.status_code == 200, resp.text
        assert any(s["id"] == str(sub.id) for s in resp.json())

    async def test_project_subcontractors_404(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(
            "/api/projects/00000000-0000-0000-0000-000000000000/subcontractors"
        )
        assert resp.status_code == 404

    async def test_quick_add_subcontractor(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        proj = await _make_project(db_session)
        email = f"quick-{uuid.uuid4().hex[:8]}@example.com"
        resp = await async_client.post(
            f"/api/projects/{proj.id}/subcontractors/quick-add",
            json={"company_name": "Quick Add Co", "email": email, "city": "Dallas"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["company_name"] == "Quick Add Co"
        assert body["email"] == email
        assert body["active_projects_count"] == 1

        dup = await async_client.post(
            f"/api/projects/{proj.id}/subcontractors/quick-add",
            json={"company_name": "Dup Co", "email": email},
        )
        assert dup.status_code == 400, dup.text

    async def test_quick_add_unknown_project(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/subcontractors/quick-add",
            json={
                "company_name": "Ghost Co",
                "email": f"ghost-{uuid.uuid4().hex[:8]}@example.com",
            },
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Certifications (top-level router)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCertificationsAPI:
    async def test_create_list_get_update_delete(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        sub = await _make_sub(db_session)

        created = await async_client.post("/api/certifications", json=_cert_payload(sub.id))
        assert created.status_code == 201, created.text
        cert = created.json()
        assert cert["certification_type"] == "OSHA 30"
        assert cert["subcontractor_id"] == str(sub.id)

        listed = await async_client.get(f"/api/certifications?subcontractor_id={sub.id}")
        assert listed.status_code == 200, listed.text
        assert any(c["id"] == cert["id"] for c in listed.json())

        fetched = await async_client.get(f"/api/certifications/{cert['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == cert["id"]

        updated = await async_client.patch(
            f"/api/certifications/{cert['id']}",
            json={"certification_type": "OSHA 10", "status": "expired"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["certification_type"] == "OSHA 10"
        assert updated.json()["status"] == "expired"

        deleted = await async_client.delete(f"/api/certifications/{cert['id']}")
        assert deleted.status_code == 204
        assert (await async_client.get(f"/api/certifications/{cert['id']}")).status_code == 404

    async def test_create_certification_unknown_sub(
        self, async_client: AsyncClient
    ) -> None:
        resp = await async_client.post(
            "/api/certifications",
            json=_cert_payload("00000000-0000-0000-0000-000000000000"),
        )
        assert resp.status_code == 404

    async def test_get_certification_404(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(
            "/api/certifications/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_contractor_certifications(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        sub = await _make_sub(db_session)
        await async_client.post("/api/certifications", json=_cert_payload(sub.id, number="C-A"))
        await async_client.post("/api/certifications", json=_cert_payload(sub.id, number="C-B"))

        resp = await async_client.get(f"/api/contractors/{sub.id}/certifications")
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert len(rows) == 2
        assert all(r["subcontractor_company_name"] == sub.company_name for r in rows)


# ---------------------------------------------------------------------------
# Violations (top-level router)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestViolationsAPI:
    async def test_create_list_get_update_delete(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        sub = await _make_sub(db_session)

        created = await async_client.post("/api/violations", json=_violation_payload(sub.id))
        assert created.status_code == 201, created.text
        viol = created.json()
        assert viol["violation_type"] == "Safety"
        assert viol["subcontractor_id"] == str(sub.id)

        listed = await async_client.get(f"/api/violations?subcontractor_id={sub.id}")
        assert listed.status_code == 200, listed.text
        assert any(v["id"] == viol["id"] for v in listed.json())

        fetched = await async_client.get(f"/api/violations/{viol['id']}")
        assert fetched.status_code == 200

        updated = await async_client.patch(
            f"/api/violations/{viol['id']}",
            json={"violation_type": "Environmental", "status": "resolved"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["violation_type"] == "Environmental"
        assert updated.json()["status"] == "resolved"

        deleted = await async_client.delete(f"/api/violations/{viol['id']}")
        assert deleted.status_code == 204
        assert (await async_client.get(f"/api/violations/{viol['id']}")).status_code == 404

    async def test_create_violation_unknown_sub(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/violations",
            json=_violation_payload("00000000-0000-0000-0000-000000000000"),
        )
        assert resp.status_code == 404

    async def test_get_violation_404(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(
            "/api/violations/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_contractor_violations(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        sub = await _make_sub(db_session)
        await async_client.post("/api/violations", json=_violation_payload(sub.id))

        resp = await async_client.get(f"/api/contractors/{sub.id}/violations")
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert len(rows) >= 1
        assert all(r["subcontractor_company_name"] == sub.company_name for r in rows)


# ---------------------------------------------------------------------------
# Compliance reads
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestComplianceReads:
    async def test_health(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/health")
        assert resp.status_code == 200

    async def test_cache_stats(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/cache/stats")
        assert resp.status_code == 200, resp.text

    async def test_compliance_status(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        await _make_sub(db_session)
        resp = await async_client.get("/api/compliance/status")
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json(), list)

    async def test_compliance_alerts(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/compliance/alerts")
        assert resp.status_code == 200, resp.text

    async def test_dashboard_summary(self, async_client: AsyncClient, db_session: AsyncSession) -> None:
        await _make_sub(db_session)
        resp = await async_client.get("/api/dashboard/summary")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "total_subcontractors" in body
