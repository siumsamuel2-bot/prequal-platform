import os
import logging
from typing import Optional
from datetime import datetime
import stripe
from stripe import Customer, Subscription
from stripe.checkout import Session as CheckoutSession

logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

PRICE_IDS = {
    "starter": os.getenv("STRIPE_PRICE_STARTER", ""),
    "professional": os.getenv("STRIPE_PRICE_PROFESSIONAL", ""),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
}

TIER_LIMITS = {
    "starter": 25,
    "professional": 100,
    "enterprise": -1,
}


def get_tier_limit(plan: str) -> int:
    return TIER_LIMITS.get(plan, 25)


def check_subcontractor_limit(plan: str, current_count: int) -> bool:
    limit = get_tier_limit(plan)
    if limit == -1:
        return True
    return current_count < limit


async def create_customer(email: str, name: str, org_id: str, metadata: Optional[dict] = None) -> Customer:
    if not stripe.api_key:
        logger.warning("Stripe API key not configured")
        return None

    extra_metadata = {"org_id": org_id}
    if metadata:
        extra_metadata.update(metadata)

    try:
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata=extra_metadata
        )
        logger.info(f"Created Stripe customer {customer.id} for org {org_id}")
        return customer
    except stripe.error.StripeError as e:
        logger.error(f"Failed to create Stripe customer: {e}")
        raise


async def create_subscription(customer_id: str, price_id: str, metadata: Optional[dict] = None) -> Subscription:
    if not stripe.api_key:
        logger.warning("Stripe API key not configured")
        return None

    try:
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            metadata=metadata or {},
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )
        logger.info(f"Created subscription {subscription.id} for customer {customer_id}")
        return subscription
    except stripe.error.StripeError as e:
        logger.error(f"Failed to create subscription: {e}")
        raise


async def get_subscription(subscription_id: str) -> Subscription:
    if not stripe.api_key:
        return None

    try:
        return stripe.Subscription.retrieve(subscription_id)
    except stripe.error.StripeError as e:
        logger.error(f"Failed to retrieve subscription {subscription_id}: {e}")
        raise


async def cancel_subscription(subscription_id: str) -> Subscription:
    if not stripe.api_key:
        return None

    try:
        subscription = stripe.Subscription.delete(subscription_id)
        logger.info(f"Cancelled subscription {subscription_id}")
        return subscription
    except stripe.error.StripeError as e:
        logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
        raise


async def create_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    org_id: str
) -> CheckoutSession:
    if not stripe.api_key:
        logger.warning("Stripe API key not configured")
        return None

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"org_id": org_id}
        )
        logger.info(f"Created checkout session {session.id} for org {org_id}")
        return session
    except stripe.error.StripeError as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise


async def create_billing_portal_session(customer_id: str, return_url: str) -> dict:
    if not stripe.api_key:
        logger.warning("Stripe API key not configured")
        return None

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url
        )
        logger.info(f"Created billing portal session for customer {customer_id}")
        return {"url": session.url}
    except stripe.error.StripeError as e:
        logger.error(f"Failed to create billing portal session: {e}")
        raise


def construct_webhook_event(payload: bytes, sig: str, secret: str) -> Optional[stripe.Event]:
    if not stripe.api_key:
        return None

    try:
        return stripe.Webhook.construct_event(payload, sig, secret)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise


def get_plan_from_price_id(price_id: str) -> Optional[str]:
    for plan, pid in PRICE_IDS.items():
        if pid == price_id:
            return plan
    return None


def get_price_id_from_plan(plan: str) -> Optional[str]:
    return PRICE_IDS.get(plan)