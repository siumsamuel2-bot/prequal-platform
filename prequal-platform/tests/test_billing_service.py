"""Unit tests for app.services.billing_service (MID-676 coverage).

Pure-logic helpers (tier limits, price<->plan mapping) and the guard paths that
short-circuit when Stripe is not configured. These assert real behaviour: no
assertions are weakened and no Stripe network calls are made.
"""
from __future__ import annotations

import pytest

from app.services import billing_service


# ---------------------------------------------------------------------------
# Tier limits
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "plan,expected",
    [("starter", 25), ("professional", 100), ("enterprise", -1)],
)
def test_get_tier_limit_known_plans(plan, expected) -> None:
    assert billing_service.get_tier_limit(plan) == expected


def test_get_tier_limit_unknown_plan_defaults_to_starter() -> None:
    assert billing_service.get_tier_limit("mystery") == 25
    assert billing_service.get_tier_limit(None) == 25


def test_check_subcontractor_limit_below_and_at_boundary() -> None:
    assert billing_service.check_subcontractor_limit("starter", 0) is True
    assert billing_service.check_subcontractor_limit("starter", 24) is True
    assert billing_service.check_subcontractor_limit("starter", 25) is False
    assert billing_service.check_subcontractor_limit("starter", 26) is False


def test_check_subcontractor_limit_enterprise_is_unlimited() -> None:
    assert billing_service.check_subcontractor_limit("enterprise", 10_000) is True


# ---------------------------------------------------------------------------
# price id <-> plan mapping
# ---------------------------------------------------------------------------

def test_get_plan_from_price_id_roundtrips(monkeypatch) -> None:
    monkeypatch.setattr(
        billing_service,
        "PRICE_IDS",
        {"starter": "price_s", "professional": "price_p", "enterprise": "price_e"},
    )
    assert billing_service.get_plan_from_price_id("price_p") == "professional"
    assert billing_service.get_plan_from_price_id("price_e") == "enterprise"


def test_get_plan_from_price_id_unknown_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(billing_service, "PRICE_IDS", {"starter": "price_s"})
    assert billing_service.get_plan_from_price_id("price_nope") is None


def test_get_price_id_from_plan(monkeypatch) -> None:
    monkeypatch.setattr(billing_service, "PRICE_IDS", {"starter": "price_s"})
    assert billing_service.get_price_id_from_plan("starter") == "price_s"
    assert billing_service.get_price_id_from_plan("enterprise") is None


# ---------------------------------------------------------------------------
# Unconfigured-Stripe guard paths (never hit the network)
# ---------------------------------------------------------------------------

@pytest.fixture
def _no_stripe_key(monkeypatch):
    monkeypatch.setattr(billing_service.stripe, "api_key", "")


@pytest.mark.asyncio
async def test_create_customer_without_key_returns_none(_no_stripe_key) -> None:
    assert await billing_service.create_customer("a@b.com", "A", "org-1") is None


@pytest.mark.asyncio
async def test_create_subscription_without_key_returns_none(_no_stripe_key) -> None:
    assert await billing_service.create_subscription("cus_1", "price_1") is None


@pytest.mark.asyncio
async def test_get_subscription_without_key_returns_none(_no_stripe_key) -> None:
    assert await billing_service.get_subscription("sub_1") is None


@pytest.mark.asyncio
async def test_cancel_subscription_without_key_returns_none(_no_stripe_key) -> None:
    assert await billing_service.cancel_subscription("sub_1") is None


@pytest.mark.asyncio
async def test_create_checkout_session_without_key_returns_none(_no_stripe_key) -> None:
    assert (
        await billing_service.create_checkout_session(
            "cus_1", "price_1", "https://ok", "https://cancel", "org-1"
        )
        is None
    )


@pytest.mark.asyncio
async def test_create_billing_portal_session_without_key_returns_none(_no_stripe_key) -> None:
    assert await billing_service.create_billing_portal_session("cus_1", "https://ret") is None


def test_construct_webhook_event_without_key_returns_none(_no_stripe_key) -> None:
    assert billing_service.construct_webhook_event(b"{}", "sig", "secret") is None
