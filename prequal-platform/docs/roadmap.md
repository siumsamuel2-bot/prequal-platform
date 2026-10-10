# Roadmap

> **Source of truth:** the ongoing-updates plan document in Paperclip
> (`/MID/issues/MID-665#document-plan`, issue MID-665). The CTO updates the plan
> document at each iteration boundary; this file mirrors its roadmap section so
> it lives with the code. If the two diverge, the plan document wins.

## Iteration cadence

- **Length: 2 weeks.** One theme, a small set of items, one demoable outcome.
  No theme-hopping mid-iteration.
- **Planning:** at iteration start the CTO selects the top items from the
  "Next up" list below and ensures each has an owner and dependencies met.
- **Priority-pull rule:** pull the highest-priority item in the active theme
  that is *ready* — (a) all dependencies done, (b) named owner. If the top item
  is blocked, pull the next ready item and record the blocker on the roadmap.
- **Signal sources (ranked):** (1) feedback/support submissions from the
  customer-care loop (MID-664); (2) pilot launch/availability gaps;
  (3) compliance/alerting correctness gaps; (4) engineering technical debt
  that blocks the next theme.

## Roadmap (next 1-2 quarters)

### Theme A — Pilot launch readiness (active)

| Item | Why it matters |
| --- | --- |
| Free-tier staging + smoke test (MID-625, MID-644) | Without a public URL there is no pilot; this is the only blocker to real usage. |
| Customer-care & feedback loop (MID-664, MID-666, MID-667) | Captures signal from day one so the roadmap is driven by real users, not guesses. |
| Design-quality pass + fail-closed UX (MID-663, MID-657) | Contractors judge the product on first impression; trust requires that unscoped/unknown access fails visibly, not silently. |
| PG-parity green (MID-656, + MID-660/661/662) | The release gate must run against real PostgreSQL before we ship to paying users. |
| Release-process doc + changelog automation (MID-668) | Makes the release path real and repeatable; every release gets a changelog. |
| In-app "What's New" surface (MID-665) | Gives customers visibility into shipping improvements each release. |

### Theme B — Daily-use value for project managers

| Item | Why it matters |
| --- | --- |
| Bulk subcontractor import (CSV) | Onboarding dozens of subs one-by-one is the #1 adoption blocker; PMs already hold this data in spreadsheets. |
| Expiration digest email (weekly) | Proactive value — PMs stop chasing expirations manually, the core promise of the product. |
| Saved dashboard views / filters | PMs revisit the same compliance cuts every day; friction here kills retention. |

### Theme C — Trust & compliance depth

| Item | Why it matters |
| --- | --- |
| Evidence document viewer with expiry highlighting | PMs must verify the credential behind a status before they trust it. |
| Branded compliance report export (PDF) | GCs forward these to owners/GIs; today that is a manual, out-of-product task. |
| Admin audit-log surface | "Who changed this" is a standard buyer question; we already log it, we just don't surface it. |

### Theme D — Self-serve growth

| Item | Why it matters |
| --- | --- |
| Self-serve signup + org creation | Removes the sales bottleneck so the pilot can convert without hand-holding. |
| Billing/subscription (Stripe) | Turns a successful pilot into revenue; `organizations.stripe_customer_id` already exists (mid-18 work). |
| Public "What's New" marketing page | Gives prospects and existing customers a reason to return and signals active development. |

## Current iteration (Iteration 1 — Pilot launch readiness)

| Item | Owner | Status |
| --- | --- | --- |
| Free-tier staging + smoke test (MID-625, MID-644) | DevOps | in flight (staging board-gated) |
| Feedback loop API + UI (MID-666, MID-667) | Backend / Frontend | in flight |
| Design-quality pass (MID-663) + fail-closed UX (MID-657) | Frontend | in flight |
| PG-parity green (MID-656 family) | Senior / Backend / Data | in flight |
| Release-process doc + changelog automation (MID-668) | DevOps | in flight |
| In-app "What's New" surface | Frontend | NEW |
