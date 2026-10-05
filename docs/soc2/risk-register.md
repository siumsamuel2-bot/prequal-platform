# Risk Register (CC3.1)

**Owner:** CTO (accepts risk) · **Maintained by:** Security Engineer · Data Engineer (this document)
**Last updated:** 2026-10-05 · **Review cadence:** quarterly + after each pentest
**Sources:** pentest backlog ([MID-275](/MID/issues/MID-275), reports `pentest_report*.md`), dependency exception register ([DEPENDENCY_PATCH_POLICY.md](../DEPENDENCY_PATCH_POLICY.md)), project issues.

**Scale:** Likelihood/Impact ∈ {Low, Medium, High, Critical}. Status ∈ {Open, Mitigating, Accepted, Closed}.

| ID | Risk | L×I | Category | Mitigation / control | Status |
|---|---|---|---|---|---|
| R-001 | Multi-tenant data isolation gap on compliance endpoints (MID-433 C1) | Critical | Data breach | Tenant-scoped queries + isolation tests (MID-459, `test_analytics_tenant_isolation.py`) | Closed (verified MID-573 retest) |
| R-002 | Hardcoded SECRET_KEY fallback in env-less deployments | High | Credential compromise | Fail-fast on missing SECRET_KEY (MID-433 H1); `test_no_hardcoded_secrets.py` | Closed |
| R-003 | Stale/unpatched dependency shipped to production | Medium | Vulnerability | CI dependency scans (pip-audit/Trivy), patch SLA, Dependabot | Mitigating |
| R-004 | Secret rotation failure → stale credential exposure | Medium | Credential compromise | Automated 90-day rotation + emergency runbook (MID-594) | Mitigating |
| R-005 | Unauthenticated brute force on auth endpoints | Medium | Account takeover | Rate limiting + account lockout (MID-593, session policy) | Closed |
| R-006 | Data-quality pipeline silently degrades (wrong compliance numbers) | Medium | Integrity | Data-quality monitoring + alert tables ([AUDIT_LOGGING.md](../AUDIT_LOGGING.md)) | Mitigating |
| R-007 | Loss of RDS instance without verified restore | High | Availability | Nightly snapshots + DR drill plan ([disaster-recovery-drill-plan.md](./disaster-recovery-drill-plan.md)) | Open — first drill scheduled |
| R-008 | Single-region deployment (no cross-region failover) | Medium | Availability | Documented DR plan; annual failover drill | Accepted (pilot) |
| R-009 | Subcontractor PII (EIN) exposure at rest | High | Confidentiality | Field-level encryption (Alembic 015/016), TLS, data-access audit log | Mitigating |
| R-010 | Insider misuse of broad read access | Medium | Insider threat | 90-day access review ([evidence/access-review-2026Q4.md](./evidence/access-review-2026Q4.md)), least-privilege roles, audit trail | Mitigating |
| R-011 | Third-party sub-processor compromise (AWS/Stripe/GitHub/Sentry) | Low | Supply chain | Vendor register + SOC2 report collection ([vendor-register.md](./vendor-register.md)) | Open — assessments pending |
| R-012 | ETL source scraping breaks silently (state board site change) | Medium | Availability of compliance data | Source-DB health checks, pipeline alerts | Mitigating |

**Change log** — entries added/closed are appended, never deleted:
- 2026-10-05: register created; seeded from MID-275 pentest backlog; R-007 opened by DR-drill plan; R-011 pending vendor collection.
