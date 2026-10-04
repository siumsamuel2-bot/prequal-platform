# Secret Rotation Runbook — Prequal Platform

Companion to [SECRETS_MANAGEMENT.md](./SECRETS_MANAGEMENT.md). Use this
document for scheduled rotations and for the emergency "secret compromised"
path (SOC 2 CC7.2 / A.12.3).

> **Policy:** every secret has a maximum lifetime of **90 days**. Secrets the
> platform fully controls are rotated automatically; provider-managed
> credentials are rotated on the same 90-day cadence by the owner below.

## Document control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-10-04 | Backend Engineer | Automated rotation + emergency procedures (MID-594) |

---

## 1. Secret inventory & rotation mode

| Secret | AWS Secrets Manager id | Rotation mode | Owner | Max lifetime |
|--------|------------------------|---------------|-------|--------------|
| JWT signing key (`SECRET_KEY`) | `prequal/api-secrets` | **Automated** | Backend | 90 days |
| Envelope encryption key (`ENCRYPTION_KEY`) | `prequal/api-secrets` | Manual (re-encrypt) | Backend | 90 days |
| OSHA API key | `prequal/api-secrets` | Manual (provider) | Backend | 90 days |
| SMTP credentials | `prequal/api-secrets` | Manual (provider) | DevOps | 90 days |
| Stripe keys | `prequal/stripe-secrets` | Manual (provider) | Backend | 90 days |
| Analytics service key | `prequal/analytics/service-auth` | Manual (coordinated) | DevOps | 90 days |
| Database password | SSM `/prequal/database-url` | Manual (RDS) | DevOps | 90 days |
| AWS deploy keys | GitHub Secrets + IAM | Manual (IAM) | DevOps | 90 days |

`SECRET_KEY` is the only self-contained value (`terraform/secret_rotation/`), so
it is the only one AWS rotates on its own. Everything else either lives with a
third party or requires an application-side data migration, and therefore has a
documented runbook below.

---

## 2. Automated rotation (JWT signing key)

**Implementation:** `terraform/secret_rotation.tf` + `terraform/secret_rotation/index.py`.

- AWS invokes the `prequal-secret-rotation` Lambda every **90 days**
  (`automatically_after_days = 90`).
- The Lambda runs the standard four steps (`createSecret` → `setSecret` →
  `testSecret` → `finishSecret`) and regenerates only the keys listed in the
  secret's `RotationKeys` tag (`SECRET_KEY`).
- Non-listed keys (`ENCRYPTION_KEY`, `OSHA_API_KEY`, SMTP) are copied through
  untouched.
- On `finishSecret` the Lambda forces a new ECS deployment so running tasks pick
  up the new value.

**Expected impact:** active sessions signed with the previous key are
invalidated. Sessions are already short-lived (15 minutes) and rotate per
request, so the blast radius is one access-token lifetime.

**Verify a rotation:**

```bash
aws secretsmanager describe-secret --secret-id prequal/api-secrets \
  --query '{LastRotated:LastRotatedDate,NextRotation:NextRotationDate,RotationEnabled:RotationEnabled}'

aws logs tail /aws/lambda/prequal-secret-rotation --since 1h
```

**Force an on-demand rotation** (e.g. suspected exposure):

```bash
aws secretsmanager rotate-secret --secret-id prequal/api-secrets
```

---

## 3. Manual rotation procedures

### 3.1 Envelope encryption key (`ENCRYPTION_KEY`)

Rotating `ENCRYPTION_KEY` makes data encrypted with the old key unreadable, so
it is **not** automated. Required sequence:

1. Announce a maintenance window; pause credential-upload traffic.
2. Provision the new key as a *versioned* value (`ENCRYPTION_KEY`,
   `ENCRYPTION_KEY_PREVIOUS`).
3. Run the re-encryption job to re-wrap stored ciphertext with the new key.
4. Deploy with the new key, confirm decrypts succeed.
5. Remove `ENCRYPTION_KEY_PREVIOUS` and update the rotation log.

### 3.2 Provider-managed credentials (Stripe, OSHA, SMTP)

1. Generate the new credential in the provider dashboard.
2. Write it into Secrets Manager:
   ```bash
   aws secretsmanager put-secret-value --secret-id prequal/stripe-secrets \
     --secret-string file://new-stripe-secrets.json
   ```
3. Force a redeploy: `aws ecs update-service --cluster prequal-cluster --service prequal-service --force-new-deployment`
4. Verify the integration (Stripe webhook test; OSHA API smoke call; test email).
5. Revoke the old credential at the provider.
6. Record the rotation in the log (section 6).

### 3.3 Database password

```bash
NEW_PW=$(openssl rand -base64 32)
aws secretsmanager put-secret-value --secret-id prequal/api-secrets \
  --secret-string "{\"DATABASE_PASSWORD\":\"$NEW_PW\"}"   # or update SSM param
aws rds modify-db-instance --db-instance-identifier prequal-db \
  --master-user-password "$NEW_PW" --apply-immediately
aws ecs update-service --cluster prequal-cluster --service prequal-service --force-new-deployment
curl -fsS https://<host>/api/health
```

### 3.4 Analytics service key

Rotate `prequal/analytics/service-auth` **only** while both the API and
analytics service are redeployed together (shared secret, no overlap window).
Put the new value, then force-new-deployment on both ECS services before
revoking anything.

---

## 4. Emergency: suspected secret compromise

Trigger this runbook when a secret appears in logs, a repo, chat, a laptop, or a
third-party breach notice.

**T+0 — Contain**
1. Do **not** delete or paste the secret anywhere new. Preserve evidence
   (CloudTrail / CloudWatch / the leaking artifact).
2. Declare an incident in the incident channel and page the on-call owner
   (see [INCIDENT_RESPONSE_PLAN.md](./INCIDENT_RESPONSE_PLAN.md)).

**T+15 min — Rotate**
3. Rotate the exposed secret immediately:
   - `SECRET_KEY` → `aws secretsmanager rotate-secret --secret-id prequal/api-secrets`
   - provider keys → section 3.2 (revoke old key as soon as the new one is live)
   - DB password → section 3.3
   - encryption key → section 3.1
4. If a key was committed to git, remove it from the tracked tree **and**
   treat the value as permanently compromised regardless of the commit date.

**T+1 h — Verify**
5. Confirm the new value is live:
   ```bash
   aws secretsmanager describe-secret --secret-id prequal/api-secrets \
     --query 'LastRotatedDate'
   aws logs tail /aws/lambda/prequal-secret-rotation --since 2h
   curl -fsS https://<host>/api/health
   ```
6. Review CloudTrail for `GetSecretValue` from unexpected principals/IPs:
   ```bash
   aws cloudtrail lookup-events \
     --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue \
     --start-time "$(date -u -d '-24 hours' +%FT%TZ)"
   ```

**Close-out**
7. Notify the CTO and, if customer data may be affected, Security & Legal.
8. File a post-incident review within 5 business days; add a regression guard
   (scan rule, test, or IAM restriction) so the same leak cannot recur.

---

## 5. Detection controls

| Control | Location |
|---------|----------|
| gitleaks scan on every push/PR | `.github/workflows/ci-cd.yml` (`secrets-scan`) |
| Standalone scanner (pre-commit + CI) | `scripts/scan_secrets.py`, `.githooks/pre-commit` |
| Secret access audit trail | CloudTrail `GetSecretValue` (per SECRETS_MANAGEMENT.md) |
| Rotation failure alarm | `/aws/lambda/prequal-secret-rotation` log group |

Install the local pre-commit guard once per clone:

```bash
git config core.hooksPath .githooks
```

---

## 6. Rotation log

Append one row per rotation. Keep this current — it is the SOC 2 evidence.

| Date | Secret | Rotated by | Mode | Verified |
|------|--------|-----------|------|----------|
| YYYY-MM-DD | `SECRET_KEY` | Name | Auto | Yes/No |
