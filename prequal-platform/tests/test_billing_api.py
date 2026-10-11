"""Billing API tests (MID-676 coverage).

Covers the billing router contract without hitting Stripe:

* public plan catalogue,
* subscription status (free vs. active, tier limit + add-more logic),
* checkout/portal validation and the unconfigured-Stripe guards,
* the webhook signature guard,
* each webhook handler (checkout completed, subscription updated/deleted,
  payment failed) driven with lightweight fake Stripe objects.

These assert real behaviour; no Stripe network calls are made.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text

from api.main import app as fastapi_app
from app.models.auth import Organization, User
from app.models.billing import Subscription, SubscriptionStatus
from app.routers import billing as billing_router
from app.routers.auth import get_current_user
from app.schemas.compliance import TokenData

PREFIX = "/api/billing"
SLUG_PREFIX = "mid676-bill-"
EMAIL_PREFIX = "mid676-bill-"


def _token(user_id) -> TokenData:
    return TokenData(
        sub=f"{str(user_id)[:8]}@example.com",
        user_id=str(user_id),
        role="admin",
        team_id=None,
    )


def _as(user_id):
    return lambda: _token(user_id)


@pytest_asyncio.fixture(autouse=True, scope="module")
async def _clean_billing(db_engine):
    async def _purge():
        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM subscriptions WHERE org_id IN "
                    "(SELECT id FROM organizations WHERE slug LIKE :p)"
                ),
                {"p": f"{SLUG_PREFIX}%"},
            )
            await conn.execute(
                text("DELETE FROM users WHERE email LIKE :p"),
                {"p": f"{EMAIL_PREFIX}%"},
            )
            await conn.execute(
                text("DELETE FROM organizations WHERE slug LIKE :p"),
                {"p": f"{SLUG_PREFIX}%"},
            )

    await _purge()
    yield
    await _purge()


async def _make_org_user(
    db,
    *,
    stripe_customer_id=None,
    plan=None,
    status=SubscriptionStatus.ACTIVE,
):
    org = Organization(
        name="Billing Org",
        slug=f"{SLUG_PREFIX}{uuid.uuid4().hex[:10]}",
        stripe_customer_id=stripe_customer_id,
    )
    db.add(org)
    await db.flush()

    user = User(
        id=uuid.uuid4(),
        email=f"{EMAIL_PREFIX}{uuid.uuid4().hex[:10]}@example.com",
        name="Billing User",
        hashed_password="x",
        role="admin",
        is_active=True,
        org_id=org.id,
    )
    db.add(user)
    await db.flush()

    sub = None
    if plan:
        sub = Subscription(
            org_id=org.id,
            plan=plan,
            status=status,
        )
        db.add(sub)
        await db.flush()

    await db.commit()
    return org, user, sub


# ---------------------------------------------------------------------------
# Plan catalogue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_plans_is_public(async_client: AsyncClient) -> None:
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    response = await async_client.get(f"{PREFIX}/plans")
    assert response.status_code == 200, response.text
    plans = {p["plan"]: p for p in response.json()}
    assert set(plans) == {"starter", "professional", "enterprise"}
    assert plans["starter"]["limit"] == 25
    assert plans["professional"]["limit"] == 100
    assert plans["enterprise"]["limit"] == -1
    assert "Up to 25 subcontractors" in plans["starter"]["features"]


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [("get", f"{PREFIX}/subscription"), ("post", f"{PREFIX}/portal")])
async def test_endpoints_require_auth(async_client: AsyncClient, method, path) -> None:
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    response = await getattr(async_client, method)(path)
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# Subscription status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscription_status_free_when_no_record(
    async_client: AsyncClient, db_session
) -> None:
    org, user, _ = await _make_org_user(db_session)
    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        response = await async_client.get(f"{PREFIX}/subscription")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "plan": "free",
        "status": "inactive",
        "current_period_end": None,
        "subcontractor_limit": 5,
        "subcontractor_count": 0,
        "can_add_more": True,
    }


@pytest.mark.asyncio
async def test_subscription_status_active_plan(
    async_client: AsyncClient, db_session
) -> None:
    org, user, _ = await _make_org_user(db_session, plan="professional")
    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        response = await async_client.get(f"{PREFIX}/subscription")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["plan"] == "professional"
    assert body["status"] == "active"
    assert body["subcontractor_limit"] == 100
    assert body["subcontractor_count"] == 0
    assert body["can_add_more"] is True


@pytest.mark.asyncio
async def test_subscription_status_no_org_returns_404(
    async_client: AsyncClient, db_session
) -> None:
    user = User(
        id=uuid.uuid4(),
        email=f"{EMAIL_PREFIX}noorg-{uuid.uuid4().hex[:8]}@example.com",
        name="No Org",
        hashed_password="x",
        role="admin",
        is_active=True,
        org_id=None,
    )
    db_session.add(user)
    await db_session.commit()

    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        response = await async_client.get(f"{PREFIX}/subscription")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_rejects_unknown_plan(
    async_client: AsyncClient, db_session
) -> None:
    org, user, _ = await _make_org_user(db_session, stripe_customer_id="cus_abc")
    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        response = await async_client.post(f"{PREFIX}/checkout?plan=bogus")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Invalid plan"


@pytest.mark.asyncio
async def test_checkout_without_stripe_customer_returns_400(
    async_client: AsyncClient, db_session
) -> None:
    org, user, _ = await _make_org_user(db_session)
    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        response = await async_client.post(f"{PREFIX}/checkout?plan=starter")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 400, response.text
    assert "No Stripe customer" in response.json()["detail"]


@pytest.mark.asyncio
async def test_checkout_without_price_config_returns_400(
    async_client: AsyncClient, db_session
) -> None:
    org, user, _ = await _make_org_user(db_session, stripe_customer_id="cus_abc")
    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        response = await async_client.post(f"{PREFIX}/checkout?plan=starter")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 400, response.text
    assert "price not configured" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Portal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portal_without_stripe_customer_returns_400(
    async_client: AsyncClient, db_session
) -> None:
    org, user, _ = await _make_org_user(db_session)
    fastapi_app.dependency_overrides[get_current_user] = _as(user.id)
    try:
        response = await async_client.post(f"{PREFIX}/portal")
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 400, response.text
    assert "No Stripe customer" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Webhook guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_missing_signature_returns_400(async_client: AsyncClient) -> None:
    response = await async_client.post(f"{PREFIX}/webhook", content=b"{}")
    assert response.status_code == 400, response.text
    assert "signature" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Webhook handlers (called directly with fake Stripe objects)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_checkout_completed_sets_customer_id(db_session) -> None:
    org, _, _ = await _make_org_user(db_session)
    session = SimpleNamespace(
        metadata={"org_id": str(org.id)},
        customer="cus_new",
        subscription=None,
    )
    await billing_router.handle_checkout_completed(session, db_session)
    await db_session.refresh(org)
    assert org.stripe_customer_id == "cus_new"


@pytest.mark.asyncio
async def test_handle_checkout_completed_missing_org_id_is_noop(db_session) -> None:
    org, _, _ = await _make_org_user(db_session)
    session = SimpleNamespace(metadata={}, customer="cus_x", subscription=None)
    await billing_router.handle_checkout_completed(session, db_session)
    await db_session.refresh(org)
    assert org.stripe_customer_id is None


@pytest.mark.asyncio
async def test_handle_checkout_completed_unknown_org_is_noop(db_session) -> None:
    session = SimpleNamespace(
        metadata={"org_id": str(uuid.uuid4())},
        customer="cus_x",
        subscription=None,
    )
    await billing_router.handle_checkout_completed(session, db_session)


@pytest.mark.asyncio
async def test_handle_subscription_updated_creates_subscription(db_session) -> None:
    org, _, _ = await _make_org_user(db_session)
    stripe_sub = SimpleNamespace(
        metadata={"org_id": str(org.id)},
        items=SimpleNamespace(data=[]),
        status="active",
        id="sub_new",
        current_period_end=1_700_000_000,
    )
    await billing_router.handle_subscription_updated(stripe_sub, db_session)

    stored = (
        await db_session.execute(
            select(Subscription).where(Subscription.org_id == org.id)
        )
    ).scalar_one()
    assert stored.plan == "starter"
    assert stored.stripe_subscription_id == "sub_new"
    assert stored.status == SubscriptionStatus.ACTIVE


@pytest.mark.asyncio
async def test_handle_subscription_updated_falls_back_to_price_metadata(db_session) -> None:
    org, _, _ = await _make_org_user(db_session)
    stripe_sub = SimpleNamespace(
        metadata={},
        items=SimpleNamespace(
            data=[
                SimpleNamespace(
                    price=SimpleNamespace(id="price_x", metadata={"org_id": str(org.id)})
                )
            ]
        ),
        status="past_due",
        id="sub_price",
        current_period_end=1_700_000_000,
    )
    await billing_router.handle_subscription_updated(stripe_sub, db_session)

    stored = (
        await db_session.execute(
            select(Subscription).where(Subscription.org_id == org.id)
        )
    ).scalar_one()
    assert stored.stripe_subscription_id == "sub_price"
    assert stored.status == SubscriptionStatus.PAST_DUE


@pytest.mark.asyncio
async def test_handle_subscription_updated_no_org_is_noop(db_session) -> None:
    stripe_sub = SimpleNamespace(
        metadata={},
        items=SimpleNamespace(data=[]),
        status="active",
        id="sub_orphan",
        current_period_end=1_700_000_000,
    )
    await billing_router.handle_subscription_updated(stripe_sub, db_session)


@pytest.mark.asyncio
async def test_handle_subscription_deleted_cancels(db_session) -> None:
    org, _, sub = await _make_org_user(db_session, plan="starter")
    stripe_sub = SimpleNamespace(metadata={"org_id": str(org.id)})
    await billing_router.handle_subscription_deleted(stripe_sub, db_session)
    await db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.CANCELLED
    assert sub.canceled_at is not None


@pytest.mark.asyncio
async def test_handle_subscription_deleted_no_org_is_noop(db_session) -> None:
    stripe_sub = SimpleNamespace(metadata={})
    await billing_router.handle_subscription_deleted(stripe_sub, db_session)


@pytest.mark.asyncio
async def test_handle_payment_failed_is_noop_log_only(db_session) -> None:
    invoice = SimpleNamespace(customer="cus_fail")
    await billing_router.handle_payment_failed(invoice, db_session)
