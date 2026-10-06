import os
import logging
from datetime import datetime
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.auth import User, Organization
from app.models.billing import Subscription as SubscriptionModel, SubscriptionStatus
from app.services.billing_service import (
    create_checkout_session,
    create_billing_portal_session,
    get_price_id_from_plan,
    get_tier_limit,
    check_subcontractor_limit,
)
from app.routers.auth import get_current_user, TokenData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


class SubscriptionStatusResponse(BaseModel):
    plan: str
    status: str
    current_period_end: Optional[str] = None
    subcontractor_limit: int
    subcontractor_count: int
    can_add_more: bool


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class PlanInfo(BaseModel):
    plan: str
    name: str
    price: str
    limit: int
    features: list[str]


AVAILABLE_PLANS = {
    "starter": PlanInfo(
        plan="starter",
        name="Starter",
        price="$99/month",
        limit=25,
        features=["Up to 25 subcontractors", "Basic compliance tracking", "Email alerts", "Standard reports"]
    ),
    "professional": PlanInfo(
        plan="professional",
        name="Professional",
        price="$249/month",
        limit=100,
        features=["Up to 100 subcontractors", "Advanced compliance tracking", "SMS & email alerts", "Custom reports", "API access"]
    ),
    "enterprise": PlanInfo(
        plan="enterprise",
        name="Enterprise",
        price="$499/month",
        limit=-1,
        features=["Unlimited subcontractors", "Full compliance suite", "All alert channels", "Custom integrations", "Dedicated account manager"]
    ),
}


async def get_org_for_user(db: AsyncSession, user: TokenData) -> Organization:
    result = await db.execute(select(User).where(User.id == UUID(user.user_id)))
    db_user = result.scalar_one_or_none()
    if not db_user or not db_user.org_id:
        raise HTTPException(status_code=404, detail="No organization found")
    result = await db.execute(select(Organization).where(Organization.id == db_user.org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/plans", response_model=list[PlanInfo])
async def list_plans():
    return list(AVAILABLE_PLANS.values())


@router.get("/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    org = await get_org_for_user(db, current_user)

    result = await db.execute(
        select(SubscriptionModel).where(SubscriptionModel.org_id == org.id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return SubscriptionStatusResponse(
            plan="free",
            status="inactive",
            current_period_end=None,
            subcontractor_limit=5,
            subcontractor_count=0,
            can_add_more=True
        )

    from app.models.compliance import Subcontractor
    count_result = await db.execute(
        select(SubscriptionModel).where(SubscriptionModel.org_id == org.id)
    )
    sub_count_result = await db.execute(select(Subcontractor).where(Subcontractor.org_id == org.id))
    subcontractor_count = len(sub_count_result.scalars().all())

    plan = subscription.plan or "starter"
    limit = get_tier_limit(plan)
    can_add = check_subcontractor_limit(plan, subcontractor_count)

    return SubscriptionStatusResponse(
        plan=plan,
        status=subscription.status.value if subscription.status else "inactive",
        current_period_end=subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        subcontractor_limit=limit,
        subcontractor_count=subcontractor_count,
        can_add_more=can_add
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_subscription_checkout(
    plan: str = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if plan not in AVAILABLE_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    org = await get_org_for_user(db, current_user)
    user_result = await db.execute(select(User).where(User.id == UUID(current_user.user_id)))
    user = user_result.scalar_one_or_none()

    result = await db.execute(
        select(SubscriptionModel).where(SubscriptionModel.org_id == org.id)
    )
    existing = result.scalar_one_or_none()

    if existing and existing.stripe_customer_id:
        customer_id = existing.stripe_customer_id
    else:
        customer_id = org.stripe_customer_id

    if not customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer. Please contact support.")

    price_id = get_price_id_from_plan(plan)
    if not price_id:
        raise HTTPException(status_code=400, detail="Stripe price not configured for this plan")

    base_url = os.getenv("APP_BASE_URL", "http://localhost:3000")
    checkout_session = await create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url=f"{base_url}/settings/billing?success=true",
        cancel_url=f"{base_url}/settings/billing?cancelled=true",
        org_id=str(org.id)
    )

    if not checkout_session:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    return CheckoutResponse(checkout_url=checkout_session.url)


@router.post("/portal", response_model=PortalResponse)
async def create_billing_portal(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    org = await get_org_for_user(db, current_user)

    if not org.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found")

    base_url = os.getenv("APP_BASE_URL", "http://localhost:3000")
    portal_session = await create_billing_portal_session(
        customer_id=org.stripe_customer_id,
        return_url=f"{base_url}/settings/billing"
    )

    if not portal_session:
        raise HTTPException(status_code=500, detail="Failed to create billing portal session")

    return PortalResponse(portal_url=portal_session["url"])


class CheckoutSessionCreate(BaseModel):
    plan: str


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not sig or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Missing stripe signature")

    from app.services.billing_service import construct_webhook_event
    event = construct_webhook_event(payload, sig, STRIPE_WEBHOOK_SECRET)

    if not event:
        raise HTTPException(status_code=400, detail="Invalid webhook")

    if event.type == "checkout.session.completed":
        session = event.data.object
        await handle_checkout_completed(session, db)

    elif event.type == "customer.subscription.updated":
        subscription = event.data.object
        await handle_subscription_updated(subscription, db)

    elif event.type == "customer.subscription.deleted":
        subscription = event.data.object
        await handle_subscription_deleted(subscription, db)

    elif event.type == "invoice.payment_failed":
        invoice = event.data.object
        await handle_payment_failed(invoice, db)

    return {"received": True}


async def handle_checkout_completed(session, db: AsyncSession):
    org_id = session.metadata.get("org_id")
    if not org_id:
        logger.error("No org_id in checkout session metadata")
        return

    result = await db.execute(select(Organization).where(Organization.id == UUID(org_id)))
    org = result.scalar_one_or_none()
    if not org:
        logger.error(f"Organization {org_id} not found")
        return

    org.stripe_customer_id = session.customer
    await db.commit()

    subscription_id = session.subscription
    if subscription_id:
        from app.services.billing_service import get_subscription
        stripe_sub = await get_subscription(subscription_id)
        if stripe_sub:
            await save_subscription(org.id, stripe_sub, db)

    logger.info(f"Completed checkout for org {org_id}")


async def handle_subscription_updated(stripe_subscription, db: AsyncSession):
    org_id = stripe_subscription.metadata.get("org_id")
    if not org_id:
        for item in stripe_subscription.items.data:
            if item.price and item.price.metadata:
                org_id = item.price.metadata.get("org_id")
                break

    if not org_id:
        logger.warning("No org_id in subscription metadata")
        return

    await save_subscription(UUID(org_id), stripe_subscription, db)
    logger.info(f"Updated subscription for org {org_id}")


async def handle_subscription_deleted(stripe_subscription, db: AsyncSession):
    org_id = stripe_subscription.metadata.get("org_id")
    if not org_id:
        logger.warning("No org_id in deleted subscription")
        return

    result = await db.execute(
        select(SubscriptionModel).where(SubscriptionModel.org_id == UUID(org_id))
    )
    subscription = result.scalar_one_or_none()
    if subscription:
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.canceled_at = datetime.utcnow()
        await db.commit()

    logger.info(f"Deleted subscription for org {org_id}")


async def handle_payment_failed(invoice, db: AsyncSession):
    logger.warning(f"Payment failed for customer {invoice.customer}")


async def save_subscription(org_id: UUID, stripe_subscription, db: AsyncSession):
    from app.services.billing_service import get_plan_from_price_id

    price_id = None
    if stripe_subscription.items and stripe_subscription.items.data:
        price_id = stripe_subscription.items.data[0].price.id

    plan = get_plan_from_price_id(price_id) if price_id else "starter"

    result = await db.execute(
        select(SubscriptionModel).where(SubscriptionModel.org_id == org_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.plan = plan
        subscription.status = SubscriptionStatus.ACTIVE if stripe_subscription.status == "active" else SubscriptionStatus.PAST_DUE
        subscription.stripe_subscription_id = stripe_subscription.id
        subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
    else:
        subscription = SubscriptionModel(
            org_id=org_id,
            stripe_subscription_id=stripe_subscription.id,
            plan=plan,
            status=SubscriptionStatus.ACTIVE if stripe_subscription.status == "active" else SubscriptionStatus.PAST_DUE,
            current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end)
        )
        db.add(subscription)

    await db.commit()