# SOC 2 Controls Mapping (CC1–CC9)

**Owner:** Data Engineer (maintenance) — **Approver:** CTO
**Last updated:** 2026-10-05
**Scope:** Prequal platform (backend API, analytics service, identity service, CI/CD, AWS infrastructure).
**Related:** [MID-635](/MID/issues/MID-635), [MID-291](/MID/issues/MID-291), evidence procedures in [evidence-collection.md](./evidence-collection.md), audit checklist in [compliance-checklist.md](./compliance-checklist.md).

This document maps the implemented platform controls to the AICPA Trust Services
Common Criteria (CC1–CC9). Each control cites the artifact(s) an auditor should
inspect. Gaps are marked **GAP** and tracked in the checklist.

---

## CC1 — Control Environment

| Control | Implementation | Evidence artifact |
|---|---|---|
| CC1.1 Governance & oversight | CTO owns security program; quarterly reviews | [information-security-policy.md](./information-security-policy.md) §3 |
| CC1.2 Board oversight | Board reviews via Paperclip tasks/approvals | MID-291 issue thread |
| CC1.3 Structure, authority, responsibility | Role-based ownership (Security Engineer, Data Engineer, DevOps) declared per policy doc | Policy headers (e.g. [DEPENDENCY_PATCH_POLICY.md](../DEPENDENCY_PATCH_POLICY.md)) |
| CC1.4 Commitment to competence | Code review rotation, PR template | [CODE_REVIEW_ROTATION.md](../CODE_REVIEW_ROTATION.md), [PULL_REQUEST_TEMPLATE.md](../../.github/PULL_REQUEST_TEMPLATE.md) |
| CC1.5 Accountability | CODEOWNERS enforced on PRs | [.github/CODEOWNERS](../../.github/CODEOWNERS) |

## CC2 — Communication & Information

| Control | Implementation | Evidence artifact |
|---|---|---|
| CC2.1 Information quality | Data quality monitoring pipeline with audit events | [AUDIT_LOGGING.md](../AUDIT_LOGGING.md), `app/services/data_quality_*` |
| CC2.2 Internal communication | Incident response plan distribution | [INCIDENT_RESPONSE_PLAN.md](../INCIDENT_RESPONSE_PLAN.md) |
| CC2.3 External communication | Security policy published, disclosure contact | [SECURITY_POLICY.md](../../SECURITY_POLICY.md) |

## CC3 — Risk Assessment

| Control | Implementation | Evidence artifact |
|---|---|---|
| CC3.1 Risk identification | Annual risk assessment; periodic penetration tests | [mid573 pentest report](../../pentest_report_mid573.md) |
| CC3.2 Risk analysis | Vulnerability SLAs by severity | [DEPENDENCY_PATCH_POLICY.md](../DEPENDENCY_PATCH_POLICY.md) §2 |
| CC3.3 Fraud consideration | Authentication audit logging, anomalous-access alerts | [AUDIT_LOGGING.md](../AUDIT_LOGGING.md) |
| CC3.4 Change risk assessment | Mandatory PR + staging deployment before production | [ci-cd workflow](../../.github/workflows/ci-cd.yml) |

## CC4 — Monitoring Activities

| Control | Implementation | Evidence artifact |
|---|---|---|
| CC4.1 Ongoing monitoring | Prometheus metrics, CloudWatch alarms, uptime checks, Sentry error tracking | [MONITORING_SETUP_SUMMARY.md](../MONITORING_SETUP_SUMMARY.md), [CLOUDWATCH_ALARMS.md](../CLOUDWATCH_ALARMS.md), [UPTIME_MONITORING.md](../UPTIME_MONITORING.md), [SENTRY_SETUP.md](../SENTRY_SETUP.md) |
| CC4.2 Deficiency evaluation | CI gates fail on critical/high dependency findings | [dependency-security.yml](../../.github/workflows/dependency-security.yml) |

## CC5 — Control Activities

| Control | Implementation | Evidence artifact |
|---|---|---|
| CC5.1 Control selection | Controls documented per policy; mapped here | This document |
| CC5.2 Technology controls | Centralized secrets management via AWS Secrets Manager | [SECRETS_MANAGEMENT.md](../SECRETS_MANAGEMENT.md) |
| CC5.3 Deployment control | CodeDeploy hooks + deployment runbook | [DEPLOYMENT_RUNBOOK.md](../DEPLOYMENT_RUNBOOK.md) |

## CC6 — Logical & Physical Access

| Control | Implementation | Evidence artifact |
|---|---|---|
| CC6.1 Least privilege & authentication | JWT auth, RBAC, org/tenant isolation, MFA (MID-315) | [access-control-policy.md](./access-control-policy.md), `app/routers/auth.py`, TOTP tests |
| CC6.2 Credential management | 90-day secret rotation (automated + manual paths) | [SECRET_ROTATION_RUNBOOK.md](../SECRET_ROTATION_RUNBOOK.md) |
| CC6.3 Access removal/review | 90-day user access reviews (policy) | [information-security-policy.md](./information-security-policy.md) §6 — **GAP: review log not yet produced** |
| CC6.7 Data-in-transit protection | TLS enforced via ACM/ALB | [terraform/](../../terraform/), [ssl cert management] |
| CC6.8 Data-at-rest protection | PII field encryption (EIN etc.) for subcontractors | Alembic migrations `015/016_encrypt_subcontractor_*` |

## CC7 — System Operations

| Control | Implementation | Evidence artifact |
|---|---|---|
| CC7.1 Vulnerability detection | Continuous dependency scanning (pip-audit/npm audit/Trivy), semgrep SAST, gitleaks | [dependency-security.yml](../../.github/workflows/dependency-security.yml), [.semgrep.yml](../../.semgrep.yml), [.gitleaks.toml](../../.gitleaks.toml) |
| CC7.2 Incident management | Incident response plan + emergency rotation path | [incident-response-plan.md](./incident-response-plan.md), [SECRET_ROTATION_RUNBOOK.md](../SECRET_ROTATION_RUNBOOK.md) |
| CC7.3 Event monitoring | Structured JSON logs, correlation IDs, data-access audit trail | [AUDIT_LOGGING.md](../AUDIT_LOGGING.md), `app/middleware/correlation_id.py` |
| CC7.4 Business continuity | Disaster recovery plan | [disaster-recovery-plan.md](./disaster-recovery-plan.md) |

## CC8 — Change Management

| Control | Implementation | Evidence artifact |
|---|---|---|
| CC8.1 Change authorization/testing | PR approval required, CI must pass, staged rollout via staging → production workflows | [change-management-policy.md](./change-management-policy.md), [.github/workflows/](../../.github/workflows/) |

## CC9 — Risk Mitigation (Vendor & Business Continuity)

| Control | Implementation | Evidence artifact |
|---|---|---|
| CC9.1 Vendor management | Third-party dependency policy & exception register | [DEPENDENCY_PATCH_POLICY.md](../DEPENDENCY_PATCH_POLICY.md) §Exceptions — **GAP: formal vendor assessment records** |
| CC9.2 Backup/availability | DR plan, CloudWatch alarms | [disaster-recovery-plan.md](./disaster-recovery-plan.md) |

---

## Control gaps (summary — detail in checklist)

1. **CC6.3** — no quarterly access-review evidence artifact produced yet (scheduled procedure only).
2. **CC9.1** — vendor assessments informal; no supplier register.
3. **CC3.1** — risk register exists as pentest backlog, not a formal living register.
4. **CC4.2** — recurring control-self-assessment minutes not yet produced.
