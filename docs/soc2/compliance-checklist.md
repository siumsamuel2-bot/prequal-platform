# SOC 2 Readiness Compliance Checklist

**Owner:** Data Engineer — **Approver:** CTO
**Last updated:** 2026-10-05
**Legend:** ✅ implemented+evidenced · 🟡 implemented, evidence pending · 🔴 gap (action needed)

Companion to [controls-mapping.md](./controls-mapping.md) and
[evidence-collection.md](./evidence-collection.md).

## CC1 — Control Environment
- [✅] Security program owner named (CTO), quarterly review policy
- [✅] Role ownership documented in policy headers (Security/Data/DevOps)
- [✅] CODEOWNERS + PR review enforced
- [🟡] Quarterly security review minutes — first cycle not yet archived
- [🟡] Formal risk register — currently tracked as pentest backlog only

## CC2 — Communication & Information
- [✅] Security policy + disclosure contact published
- [✅] Incident response plan documented and distributed
- [✅] Data-quality monitoring implemented (audit taxonomy documented)

## CC3 — Risk Assessment
- [✅] Penetration test executed (MID-573 report) with findings tracked
- [✅] Vulnerability SLAs defined by severity
- [🟡] Living risk register to be established from pentest backlog

## CC4 — Monitoring Activities
- [✅] Prometheus/CloudWatch/Sentry/uptime monitoring live
- [✅] CI gates block critical/high dependency findings
- [🟡] Monthly monitoring evidence export not yet scheduled as routine

## CC5 — Control Activities
- [✅] Controls mapped (this package)
- [✅] Centralized secrets management (AWS Secrets Manager)
- [✅] Controlled deployments via runbook + CodeDeploy hooks

## CC6 — Logical & Physical Access
- [✅] JWT auth, RBAC, tenant isolation
- [✅] MFA for administrative access (MID-315; tests in place)
- [✅] 90-day automated secret rotation (MID-594)
- [✅] Data-at-rest encryption of subcontractor PII (Alembic 015/016)
- [✅] TLS in transit (ACM/ALB)
- [🔴] Quarterly access-review evidence — procedure defined, first run pending
- [🔴] Seed `docs/soc2/evidence/access-review-YYYYQn.md` this quarter

## CC7 — System Operations
- [✅] Dependency scanning + SAST + secrets detection in CI
- [✅] Incident response plan + emergency rotation path
- [✅] Structured audit logs + correlation IDs on all requests
- [🔴] First DR drill not executed (CC7.4/CC9.2)

## CC8 — Change Management
- [✅] PR approval + CI + staged rollout enforced

## CC9 — Risk Mitigation / Vendor & Continuity
- [✅] Dependency exception register in patch policy
- [🟡] Formal vendor assessment register missing (AWS/GHA/payment providers)
- [🔴] DR drill to validate RTO/RPO

---

## Audit-readiness priority actions (before external audit)

1. **Run first quarterly access review** (CC6.3) — Data Engineer runs extract; CTO approves.
2. **Execute DR drill** (CC9.2) — measure against RTO/RPO in DR plan; file minutes.
3. **Create vendor register** (CC9.1) — one page per critical vendor w/ SOC2 report refs.
4. **Formalize risk register** (CC3.1) — migrate pentest backlog into dated register.
5. **Archive first monitoring evidence export** (CC4.2) — set a monthly reminder routine.

## Pilot scope note

For the customer pilot, items 1–2 are required before go-live per
[launch checklist](../LAUNCH_DAY_RUNBOOK.md); items 3–5 can complete during the
pilot quarter. Update this checklist as evidence lands (never delete rows —
mark archived with dates).
