"""Feedback API tests (MID-666).

Covers the customer-care loop backend contract:
* authentication is required on every endpoint,
* org isolation (org A cannot read or patch org B's submissions),
* the disposition-note rule for ``declined``/``duplicate``,
* org scoping is derived server-side from the token (never the client).
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text

from api.main import app as fastapi_app
from app.models.auth import Organization, OrganizationMembership, User
from app.models.feedback import FeedbackSubmission
from app.routers.auth import get_current_user
from app.schemas.compliance import TokenData

PREFIX = "/api/v1/feedback"


def _token(user_id, role: str = "member", team_id=None) -> TokenData:
    return TokenData(
        sub=f"{str(user_id)[:8]}@example.com",
        user_id=str(user_id),
        role=role,
        team_id=str(team_id) if team_id else None,
    )


def _as(user_id, role: str = "member", team_id=None):
    return lambda: _token(user_id, role, team_id)


@pytest_asyncio.fixture(autouse=True)
async def _clean_feedback(db_engine):
    """Keep feedback rows from leaking across tests (module shares one DB)."""
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM feedback_submissions"))
    yield
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM feedback_submissions"))


async def _make_user(db, org_id, role="member"):
    user = User(
        id=uuid.uuid4(),
        email=f"u-{uuid.uuid4().hex[:10]}@example.com",
        name="User",
        hashed_password="x",
        role=role,
        is_active=True,
        org_id=org_id,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_org(db, owner_user_id):
    org = Organization(name="Org", slug=f"org-{uuid.uuid4().hex[:10]}")
    db.add(org)
    await db.flush()
    return org


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("post", PREFIX),
        ("get", PREFIX),
        ("patch", f"{PREFIX}/{uuid.uuid4()}"),
    ],
)
async def test_endpoints_require_auth(async_client: AsyncClient, method, path) -> None:
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    body = {"type": "comment", "surface": "analytics_dashboard", "message": "hi"}
    kwargs = {"json": body} if method != "get" else {}
    response = await getattr(async_client, method)(path, **kwargs)
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# Submission is org-derived from the token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_derives_org_from_token_and_ignores_client_org(
    async_client: AsyncClient, db_session
) -> None:
    org_a = await _make_org(db_session, None)
    attacker_org = await _make_org(db_session, None)
    user = await _make_user(db_session, org_a.id)
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        response = await async_client.post(
            PREFIX,
            json={
                "type": "rating",
                "surface": "compliance_dashboard",
                "rating": 5,
                # client-supplied org must never be honoured
                "org_id": str(attacker_org.id),
            },
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["org_id"] == str(org_a.id)
    assert body["org_id"] != str(attacker_org.id)
    assert body["user_id"] == str(user.id)
    assert body["status"] == "new"

    stored = (await db_session.execute(select(FeedbackSubmission))).scalars().all()
    assert len(stored) == 1
    assert str(stored[0].org_id) == str(org_a.id)


@pytest.mark.asyncio
async def test_post_validates_rating_and_type(async_client: AsyncClient, db_session) -> None:
    org = await _make_org(db_session, None)
    user = await _make_user(db_session, org.id)
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        bad_rating = await async_client.post(
            PREFIX, json={"type": "rating", "surface": "dash", "rating": 9}
        )
        bad_type = await async_client.post(
            PREFIX, json={"type": "nonsense", "surface": "dash"}
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert bad_rating.status_code == 422
    assert bad_type.status_code == 422


@pytest.mark.asyncio
async def test_post_fails_closed_without_org(async_client: AsyncClient, db_session) -> None:
    user = await _make_user(db_session, org_id=None)
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        response = await async_client.post(
            PREFIX, json={"type": "comment", "surface": "dash", "message": "hi"}
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403, response.text


# ---------------------------------------------------------------------------
# Org isolation for reads / patches
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def two_orgs(db_session):
    """Two orgs, each with an owner and one submission."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    db_session.add_all([
        Organization(id=org_a, name="A", slug=f"a-{org_a.hex[:8]}"),
        Organization(id=org_b, name="B", slug=f"b-{org_b.hex[:8]}"),
    ])
    await db_session.flush()

    owner_a = await _make_user(db_session, org_a)
    owner_b = await _make_user(db_session, org_b)
    await db_session.flush()

    db_session.add_all([
        OrganizationMembership(user_id=owner_a.id, org_id=org_a, role="owner"),
        OrganizationMembership(user_id=owner_b.id, org_id=org_b, role="owner"),
    ])

    sub_a = FeedbackSubmission(
        org_id=org_a, user_id=owner_a.id, type="comment",
        surface="dash", message="from A", status="new",
    )
    sub_b = FeedbackSubmission(
        org_id=org_b, user_id=owner_b.id, type="comment",
        surface="dash", message="from B", status="new",
    )
    db_session.add_all([sub_a, sub_b])
    await db_session.commit()

    yield {
        "org_a": org_a, "org_b": org_b,
        "owner_a": owner_a.id, "owner_b": owner_b.id,
        "sub_a": sub_a.id, "sub_b": sub_b.id,
    }


@pytest.mark.asyncio
async def test_get_is_org_scoped(async_client: AsyncClient, two_orgs) -> None:
    fastapi_app.dependency_overrides[get_current_user] = _as(two_orgs["owner_a"])
    try:
        response = await async_client.get(PREFIX)
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    body = response.json()
    ids = {row["id"] for row in body["items"]}
    assert str(two_orgs["sub_a"]) in ids
    assert str(two_orgs["sub_b"]) not in ids
    assert body["total"] == 1
    assert response.headers.get("X-Total-Count") == "1"


@pytest.mark.asyncio
async def test_get_returns_items_total_envelope(async_client: AsyncClient, two_orgs) -> None:
    """GET /feedback must mirror the frontend ``{items, total}`` contract.

    Regression for MID-696: a bare array body made ``response.items`` undefined
    in the admin review view, so submissions never rendered.
    """
    fastapi_app.dependency_overrides[get_current_user] = _as(two_orgs["owner_a"])
    try:
        response = await async_client.get(PREFIX)
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    assert set(body) >= {"items", "total"}
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)


@pytest.mark.asyncio
async def test_get_total_counts_beyond_page(async_client: AsyncClient, db_session) -> None:
    """``total`` is the unpaginated count; ``items`` is the requested page."""
    org = uuid.uuid4()
    db_session.add(Organization(id=org, name="P", slug=f"p-{org.hex[:8]}"))
    await db_session.flush()
    owner = await _make_user(db_session, org)
    db_session.add(OrganizationMembership(user_id=owner.id, org_id=org, role="owner"))
    db_session.add_all([
        FeedbackSubmission(org_id=org, user_id=owner.id, type="comment",
                           surface="dash", message=f"m{i}", status="new")
        for i in range(3)
    ])
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _as(owner.id)
    try:
        response = await async_client.get(PREFIX, params={"limit": 1})
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_get_other_org_owner_sees_only_own(async_client: AsyncClient, two_orgs) -> None:
    fastapi_app.dependency_overrides[get_current_user] = _as(two_orgs["owner_b"])
    try:
        response = await async_client.get(PREFIX)
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    ids = {row["id"] for row in response.json()["items"]}
    assert str(two_orgs["sub_b"]) in ids
    assert str(two_orgs["sub_a"]) not in ids


@pytest.mark.asyncio
async def test_patch_cannot_touch_other_org(async_client: AsyncClient, two_orgs, db_session) -> None:
    fastapi_app.dependency_overrides[get_current_user] = _as(two_orgs["owner_a"])
    try:
        response = await async_client.patch(
            f"{PREFIX}/{two_orgs['sub_b']}", json={"status": "triaged"}
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404, response.text
    row = await db_session.get(FeedbackSubmission, two_orgs["sub_b"])
    assert row.status == "new"


@pytest.mark.asyncio
async def test_patch_own_org_succeeds(async_client: AsyncClient, two_orgs, db_session) -> None:
    fastapi_app.dependency_overrides[get_current_user] = _as(two_orgs["owner_a"])
    try:
        response = await async_client.patch(
            f"{PREFIX}/{two_orgs['sub_a']}", json={"status": "triaged"}
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "triaged"


@pytest.mark.asyncio
async def test_non_owner_member_denied(async_client: AsyncClient, db_session) -> None:
    org = uuid.uuid4()
    db_session.add(Organization(id=org, name="C", slug=f"c-{org.hex[:8]}"))
    await db_session.flush()
    member = await _make_user(db_session, org)
    db_session.add(OrganizationMembership(user_id=member.id, org_id=org, role="member"))
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _as(member.id)
    try:
        response = await async_client.get(PREFIX)
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_admin_is_unscoped(async_client: AsyncClient, two_orgs, db_session) -> None:
    admin = await _make_user(db_session, org_id=None, role="admin")
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _as(admin.id, role="admin")
    try:
        response = await async_client.get(PREFIX)
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    ids = {row["id"] for row in response.json()["items"]}
    assert str(two_orgs["sub_a"]) in ids
    assert str(two_orgs["sub_b"]) in ids


# ---------------------------------------------------------------------------
# Disposition note rule
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_declined_requires_note(async_client: AsyncClient, two_orgs) -> None:
    fastapi_app.dependency_overrides[get_current_user] = _as(two_orgs["owner_a"])
    try:
        without_note = await async_client.patch(
            f"{PREFIX}/{two_orgs['sub_a']}", json={"status": "declined"}
        )
        blank_note = await async_client.patch(
            f"{PREFIX}/{two_orgs['sub_a']}",
            json={"status": "declined", "disposition_note": "   "},
        )
        with_note = await async_client.patch(
            f"{PREFIX}/{two_orgs['sub_a']}",
            json={"status": "declined", "disposition_note": "out of scope"},
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert without_note.status_code == 422, without_note.text
    assert blank_note.status_code == 422, blank_note.text
    assert with_note.status_code == 200, with_note.text
    assert with_note.json()["disposition_note"] == "out of scope"


@pytest.mark.asyncio
async def test_duplicate_requires_note_but_triaged_does_not(
    async_client: AsyncClient, two_orgs
) -> None:
    fastapi_app.dependency_overrides[get_current_user] = _as(two_orgs["owner_a"])
    try:
        duplicate = await async_client.patch(
            f"{PREFIX}/{two_orgs['sub_a']}", json={"status": "duplicate"}
        )
        triaged = await async_client.patch(
            f"{PREFIX}/{two_orgs['sub_a']}", json={"status": "triaged"}
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert duplicate.status_code == 422, duplicate.text
    assert triaged.status_code == 200, triaged.text


@pytest.mark.asyncio
async def test_existing_note_satisfies_rule(async_client: AsyncClient, two_orgs) -> None:
    """A note saved earlier allows a later declined transition with no new note."""
    fastapi_app.dependency_overrides[get_current_user] = _as(two_orgs["owner_a"])
    try:
        await async_client.patch(
            f"{PREFIX}/{two_orgs['sub_a']}",
            json={"status": "duplicate", "disposition_note": "seen before"},
        )
        transition = await async_client.patch(
            f"{PREFIX}/{two_orgs['sub_a']}", json={"status": "declined"}
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert transition.status_code == 200, transition.text


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filters_by_type(async_client: AsyncClient, db_session) -> None:
    org = uuid.uuid4()
    db_session.add(Organization(id=org, name="F", slug=f"f-{org.hex[:8]}"))
    await db_session.flush()
    owner = await _make_user(db_session, org)
    db_session.add(OrganizationMembership(user_id=owner.id, org_id=org, role="owner"))
    db_session.add_all([
        FeedbackSubmission(org_id=org, user_id=owner.id, type="rating",
                           surface="dash", rating=4, status="new"),
        FeedbackSubmission(org_id=org, user_id=owner.id, type="support",
                           surface="dash", message="help", status="new"),
    ])
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _as(owner.id)
    try:
        response = await async_client.get(PREFIX, params={"type": "rating"})
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    rows = response.json()["items"]
    assert len(rows) == 1
    assert rows[0]["type"] == "rating"


@pytest.mark.asyncio
async def test_patch_invalid_id_returns_422(async_client: AsyncClient, db_session) -> None:
    org = uuid.uuid4()
    db_session.add(Organization(id=org, name="G", slug=f"g-{org.hex[:8]}"))
    await db_session.flush()
    owner = await _make_user(db_session, org)
    db_session.add(OrganizationMembership(user_id=owner.id, org_id=org, role="owner"))
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _as(owner.id)
    try:
        response = await async_client.patch(f"{PREFIX}/not-a-uuid", json={"status": "triaged"})
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 422, response.text
