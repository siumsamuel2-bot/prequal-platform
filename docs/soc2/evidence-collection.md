# SOC 2 Evidence Collection Procedures

**Owner:** Data Engineer — **Approver:** CTO
**Last updated:** 2026-10-05
**Related:** [controls-mapping.md](./controls-mapping.md) (control IDs), [compliance-checklist.md](./compliance-checklist.md) (readiness status).

Each procedure below defines: **what** evidence to collect, **where** it lives,
**how** to extract it, and **frequency**. Evidence is archived under the audit
evidence folder (GitHub repo tag + S3 compliance bucket; see §7). Nothing is
ever deleted — superseded evidence is archived with a `superseded-by` pointer.

---

## 1. CC6 — Access control evidence

### 1.1 Authentication/authorization configuration (monthly)
- **What:** current auth, MFA, and RBAC configuration.
- **Where:** `prequal-platform/app/routers/auth.py`, `app/services/`, identity-service config.
- **How:** export the git tag + `git log --since` for auth paths; run the MFA/auth
  test suites and save the pytest output
  (`tests/test_mfa_and_password_policy.py`, `tests/test_auth_integration.py`).
- **Tooling:** `pytest tests/test_mfa_and_password_policy.py -v > evidence/mfa-YYYYMMDD.txt`.

### 1.2 Quarterly user access review (quarterly) — *procedure new, first run pending (GAP CC6.3)*
- **What:** list of active users/admins vs. expected roster; removals executed.
- **How:** SQL extract from `users`/`user_sessions` via read replica; file review
  minutes under `docs/soc2/evidence/access-review-YYYYQn.md`.
- **Validator:** Data Engineer runs extract; CTO signs off.

### 1.3 Secret rotation proof (per rotation / 90-day)
- **What:** rotation run logs and Secrets Manager version history.
- **Where:** automated rotation Lambda logs (see terraform `secret_rotation`),
  AWS Secrets Manager `describe-secret` output.
- **How:** follow [SECRET_ROTATION_RUNBOOK.md](../SECRET_ROTATION_RUNBOOK.md);
  capture `aws secretsmanager describe-secret` before/after.

## 2. CC7 — Operations & monitoring evidence

### 2.1 Monitoring coverage (monthly)
- **What:** active CloudWatch alarms, Sentry issue counts, uptime report.
- **How:** export alarm list per [CLOUDWATCH_ALARMS.md](../CLOUDWATCH_ALARMS.md);
  uptime report per [UPTIME_MONITORING.md](../UPTIME_MONITORING.md).

### 2.2 Audit trail integrity (monthly)
- **What:** sample of `data_access_audit_logs` proving sensitive reads/writes are logged.
- **How:** Data Engineer runs a bounded extract (last 30 days, sampled) from
  `data_access_audit_logs`; verify against [AUDIT_LOGGING.md](../AUDIT_LOGGING.md)
  taxonomy. Store aggregates only — **never export raw customer PII into evidence**.

### 2.3 Incident reports (per incident)
- **What:** incident ticket + postmortem linked to [incident-response-plan.md](./incident-response-plan.md).

## 3. CC7/CC8 — Vulnerability & change management evidence

### 3.1 Dependency scan history (per merge / weekly report)
- **What:** pip-audit / npm audit / Trivy / semgrep results.
- **How:** GitHub Actions artifacts from
  [dependency-security.yml](../../.github/workflows/dependency-security.yml);
  download run artifacts to evidence folder.

### 3.2 Patch SLA compliance (monthly)
- **What:** findings list vs. SLA table.
- **How:** compare Dependabot/scan closure timestamps against
  [DEPENDENCY_PATCH_POLICY.md](../DEPENDENCY_PATCH_POLICY.md) §2.

### 3.3 Change-management trail (per release)
- **What:** PR approvals, CI pass, staging deploy, production deploy.
- **How:** GitHub PR + Actions run IDs; production deploy per
  [DEPLOYMENT_RUNBOOK.md](../DEPLOYMENT_RUNBOOK.md). Evidence = links, not copies.

### 3.4 Penetration test reports (per engagement)
- **What:** latest pentest report and closure status of findings.
- **How:** archive [pentest_report_mid573.md](../../pentest_report_mid573.md) and
  successor reports; track finding closure in Paperclip issues.

## 4. CC2/CC4 — Data quality & information evidence

- **What:** pipeline run status, data-quality alert log.
- **How:** analytics pipeline test output and `data_quality_alerts` aggregates;
  see [AUDIT_LOGGING.md](../AUDIT_LOGGING.md).

## 5. CC9 — Business continuity evidence

### 5.1 DR test (annually) — *GAP: first DR drill not yet executed*
- **What:** DR drill minutes + recovery time measured against RTO/RPO in
  [disaster-recovery-plan.md](./disaster-recovery-plan.md).

## 6. CC1/CC3 — Governance evidence

- **What:** quarterly security review minutes, risk register snapshot.
- **How:** CTO review notes appended to `docs/soc2/evidence/reviews-YYYYQn.md`. — *GAP: first cycle pending.*

## 7. Evidence archive layout

```
docs/soc2/evidence/
├── access-review-YYYYQn.md      # CC6.3
├── mfa-YYYYMMDD.txt             # CC6.1 (pytest output)
├── monitoring-YYYYMM.md         # CC4/CC7
├── vuln-scan-<run-id>/          # CC7.1 (CI artifacts)
├── dr-drill-YYYY.md             # CC9.2
└── reviews-YYYYQn.md            # CC1/CC3
```

All evidence is committed to the repo (aggregated extracts only) and mirrored to
the compliance S3 bucket with object-lock retention. Raw production data never
enters evidence — extracts are aggregated or redacted per Data Engineer review.
