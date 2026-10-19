"""Coverage for app/services/billing_service.py (MID-676).

Drives every Stripe-backed helper through a fake ``stripe`` module (success and
``StripeError`` paths) plus the pure plan/price mapping helpers. No network.
"""
from __future__ import annotations

import types

import pytest

from app.services import billing_service


class _StripeError(Exception):
    pass


class _SignatureVerificationError(_StripeError):
    pass


def _install_stripe(
    monkeypatch,
    *,
    api_key="sk_test",
    customer=None,
    subscription=None,
    checkout_session=None,
    portal_session=None,
    event=None,
    error=None,
):
    stripe_mod = types.ModuleType("stripe")
    stripe_mod.api_key = api_key

    def _maybe_raise():
        if error is not None:
            raise error

    class _Customer:
        @staticmethod
        def create(**kwargs):
            _maybe_raise()
            return customer

    class _Subscription:
        @staticmethod
        def create(**kwargs):
            _maybe_raise()
            return subscription

        @staticmethod
        def retrieve(_id):
            _maybe_raise()
            return subscription

        @staticmethod
        def delete(_id):
            _maybe_raise()
            return subscription

    class _CheckoutSession:
        @staticmethod
        def create(**kwargs):
            _maybe_raise()
            return checkout_session

    class _PortalSession:
        @staticmethod
        def create(**kwargs):
            _maybe_raise()
            return portal_session

    class _Webhook:
        @staticmethod
        def construct_event(payload, sig, secret):
            _maybe_raise()
            return event

    stripe_mod.Customer = _Customer
    stripe_mod.Subscription = _Subscription
    stripe_mod.checkout = types.SimpleNamespace(Session=_CheckoutSession)
    stripe_mod.billing_portal = types.SimpleNamespace(Session=_PortalSession)
    stripe_mod.Webhook = _Webhook
    stripe_mod.error = types.SimpleNamespace(
        StripeError=_StripeError,
        SignatureVerificationError=_SignatureVerificationError,
    )
    monkeypatch.setattr(billing_service, "stripe", stripe_mod)
    return stripe_mod


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_get_tier_limit_and_check():
    assert billing_service.get_tier_limit("starter") == 25
    assert billing_service.get_tier_limit("professional") == 100
    assert billing_service.get_tier_limit("enterprise") == -1
    assert billing_service.get_tier_limit("unknown") == 25

    assert billing_service.check_subcontractor_limit("enterprise", 10_000) is True
    assert billing_service.check_subcontractor_limit("starter", 24) is True
    assert billing_service.check_subcontractor_limit("starter", 25) is False


def test_plan_price_mapping(monkeypatch):
    monkeypatch.setattr(
        billing_service,
        "PRICE_IDS",
        {"starter": "price_s", "professional": "price_p", "enterprise": "price_e"},
    )
    assert billing_service.get_plan_from_price_id("price_p") == "professional"
    assert billing_service.get_plan_from_price_id("nope") is None
    assert billing_service.get_price_id_from_plan("enterprise") == "price_e"
    assert billing_service.get_price_id_from_plan("nope") is None


# ---------------------------------------------------------------------------
# Stripe-backed helpers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_customer_unconfigured(monkeypatch):
    _install_stripe(monkeypatch, api_key="")
    assert await billing_service.create_customer("a@x.com", "A", "org-1") is None


@pytest.mark.asyncio
async def test_create_customer_success(monkeypatch):
    customer = types.SimpleNamespace(id="cus_1")
    _install_stripe(monkeypatch, customer=customer)
    assert await billing_service.create_customer(
        "a@x.com", "A", "org-1", metadata={"x": "y"}
    ) is customer


@pytest.mark.asyncio
async def test_create_customer_error(monkeypatch):
    _install_stripe(monkeypatch, error=_StripeError("bad"))
    with pytest.raises(_StripeError):
        await billing_service.create_customer("a@x.com", "A", "org-1")


@pytest.mark.asyncio
async def test_create_subscription_unconfigured(monkeypatch):
    _install_stripe(monkeypatch, api_key="")
    assert await billing_service.create_subscription("cus_1", "price_1") is None


@pytest.mark.asyncio
async def test_create_subscription_success(monkeypatch):
    sub = types.SimpleNamespace(id="sub_1")
    _install_stripe(monkeypatch, subscription=sub)
    assert await billing_service.create_subscription("cus_1", "price_1") is sub


@pytest.mark.asyncio
async def test_create_subscription_error(monkeypatch):
    _install_stripe(monkeypatch, error=_StripeError("bad"))
    with pytest.raises(_StripeError):
        await billing_service.create_subscription("cus_1", "price_1")


@pytest.mark.asyncio
async def test_get_subscription_unconfigured(monkeypatch):
    _install_stripe(monkeypatch, api_key="")
    assert await billing_service.get_subscription("sub_1") is None


@pytest.mark.asyncio
async def test_get_subscription_success(monkeypatch):
    sub = types.SimpleNamespace(id="sub_1")
    _install_stripe(monkeypatch, subscription=sub)
    assert await billing_service.get_subscription("sub_1") is sub


@pytest.mark.asyncio
async def test_get_subscription_error(monkeypatch):
    _install_stripe(monkeypatch, error=_StripeError("bad"))
    with pytest.raises(_StripeError):
        await billing_service.get_subscription("sub_1")


@pytest.mark.asyncio
async def test_cancel_subscription_unconfigured(monkeypatch):
    _install_stripe(monkeypatch, api_key="")
    assert await billing_service.cancel_subscription("sub_1") is None


@pytest.mark.asyncio
async def test_cancel_subscription_success(monkeypatch):
    sub = types.SimpleNamespace(id="sub_1", status="canceled")
    _install_stripe(monkeypatch, subscription=sub)
    assert await billing_service.cancel_subscription("sub_1") is sub


@pytest.mark.asyncio
async def test_cancel_subscription_error(monkeypatch):
    _install_stripe(monkeypatch, error=_StripeError("bad"))
    with pytest.raises(_StripeError):
        await billing_service.cancel_subscription("sub_1")


@pytest.mark.asyncio
async def test_create_checkout_session_unconfigured(monkeypatch):
    _install_stripe(monkeypatch, api_key="")
    assert await billing_service.create_checkout_session(
        "cus_1", "price_1", "https://ok", "https://cancel", "org-1"
    ) is None


@pytest.mark.asyncio
async def test_create_checkout_session_success(monkeypatch):
    session = types.SimpleNamespace(id="cs_1")
    _install_stripe(monkeypatch, checkout_session=session)
    assert await billing_service.create_checkout_session(
        "cus_1", "price_1", "https://ok", "https://cancel", "org-1"
    ) is session


@pytest.mark.asyncio
async def test_create_checkout_session_error(monkeypatch):
    _install_stripe(monkeypatch, error=_StripeError("bad"))
    with pytest.raises(_StripeError):
        await billing_service.create_checkout_session(
            "cus_1", "price_1", "https://ok", "https://cancel", "org-1"
        )


@pytest.mark.asyncio
async def test_create_billing_portal_unconfigured(monkeypatch):
    _install_stripe(monkeypatch, api_key="")
    assert await billing_service.create_billing_portal_session(
        "cus_1", "https://return"
    ) is None


@pytest.mark.asyncio
async def test_create_billing_portal_success(monkeypatch):
    session = types.SimpleNamespace(url="https://portal")
    _install_stripe(monkeypatch, portal_session=session)
    assert await billing_service.create_billing_portal_session(
        "cus_1", "https://return"
    ) == {"url": "https://portal"}


@pytest.mark.asyncio
async def test_create_billing_portal_error(monkeypatch):
    _install_stripe(monkeypatch, error=_StripeError("bad"))
    with pytest.raises(_StripeError):
        await billing_service.create_billing_portal_session("cus_1", "https://return")


def test_construct_webhook_unconfigured(monkeypatch):
    _install_stripe(monkeypatch, api_key="")
    assert billing_service.construct_webhook_event(b"{}", "sig", "whsec") is None


def test_construct_webhook_success(monkeypatch):
    event = types.SimpleNamespace(id="evt_1", type="invoice.paid")
    _install_stripe(monkeypatch, event=event)
    assert billing_service.construct_webhook_event(b"{}", "sig", "whsec") is event


def test_construct_webhook_bad_signature(monkeypatch):
    _install_stripe(monkeypatch, error=_SignatureVerificationError("bad sig"))
    with pytest.raises(_SignatureVerificationError):
        billing_service.construct_webhook_event(b"{}", "sig", "whsec")
