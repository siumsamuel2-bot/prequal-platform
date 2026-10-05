# Access Review — 2026 Q4 (First Run)

**Control:** SOC 2 CC6.3 (CC6.1/CC6.2) — review of logical access, least privilege
**Procedure:** per [../evidence-collection.md](../evidence-collection.md) §1.2
**Cadence:** quarterly, first week of each quarter
**Owner (extract):** Data Engineer · **Approver:** CTO
**Date performed:** 2026-10-05 (2026 Q4 cycle 1)
**Status:** ✅ COMPLETE (pre-pilot baseline)

## Scope

1. Application user accounts (`users`, `user_sessions` tables) and roles
2. Internal engineering access: GitHub org, AWS IAM, CI/CD secrets, Secrets Manager
3. Service accounts / API credentials

No customer organizations are onboarded yet (pre-pilot), so the application
portion is a baseline confirming empty state + internal access only.

## Method

### Application access extract (read-only, aggregated — no PII)

Executed against the reporting copy. Queries:

```sql
-- 1. Role/activity distribution (no emails or names in evidence)
SELECT role, is_active, mfa_enabled, COUNT(*) AS user_count
FROM users
GROUP BY role, is_active, mfa_enabled
ORDER BY role;

-- 2. Dormant/unclosed sessions older than 30 days
SELECT COUNT(*) AS stale_session_count,
       MAX(last_seen_at) AS oldest_activity
FROM user_sessions
WHERE last_seen_at < NOW() - INTERVAL '30 days';

-- 3. Orphaned accounts (no organization)
SELECT COUNT(*) AS orphaned_user_count
FROM users WHERE org_id IS NULL;

-- 4. Admin/owner access without MFA  (must be ZERO by policy)
SELECT COUNT(*) AS admin_without_mfa
FROM users
WHERE role IN ('admin', 'owner') AND is_active = true AND mfa_enabled = false;
```

### Internal access inventory

| System | Access granted to | Check performed | Result |
|---|---|---|---|
| GitHub org | Engineering team (see [CODEOWNERS](../../.github/CODEOWNERS)) | Membership vs. active roster | Baseline established |
| AWS (RDS/Secrets Manager/ECS) | DevOps + CTO | IAM principals reviewed | Baseline established |
| GitHub Actions secrets | CI only (IRSA-scoped where available) | Secret inventory per [SECRETS_MANAGEMENT.md](../SECRETS_MANAGEMENT.md) | OK |
| Stripe dashboard | CTO/finance delegate | Role review | Baseline established |

## Findings for 2026 Q4

- **Application:** 0 production customer tenants onboarded; extract queries executed
  as baseline validation. `admin_without_mfa = 0` (enforced — MFA is required for
  administrative access per [../information-security-policy.md](../information-security-policy.md) §6 and MID-315).
- **Internal:** no dormant GitHub/AWS principals identified in the pre-pilot roster.
- **Exits/offboarding:** none this quarter.

**Actions taken:** none required (clean baseline).
**Next review:** 2027 Q1, first week of January; after pilot onboarding, add
per-tenant admin listing and 90-day activity check per policy.

**Approver sign-off:** CTO — pending (record approval in Paperclip comment on
[MID-638](/MID/issues/MID-638)).
