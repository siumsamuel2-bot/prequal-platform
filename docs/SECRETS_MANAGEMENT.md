# Secrets Management - Prequal Platform

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-14 | DevOps Engineer | Initial secrets management policy |
| 1.1 | 2026-10-04 | Backend Engineer | Automated 90-day rotation + runtime loader + scan guard (MID-594); see [SECRET_ROTATION_RUNBOOK.md](./SECRET_ROTATION_RUNBOOK.md) |

---

## Overview

This document defines the secrets management policy and procedures for the Prequal Platform. It covers storage, rotation, access, and audit requirements.

---

## Principles

1. **No secrets in code** - Never commit secrets to version control
2. **Least privilege access** - Only grant access to those who need it
3. **Automatic rotation** - Rotate secrets on a regular schedule
4. **Audit all access** - Log all secret access for compliance
5. **Encryption at rest** - All secrets encrypted when stored

---

## Secret Types and Storage

### Production Secrets

| Secret Type | Storage Location | Rotation Schedule | Owner |
|-------------|------------------|-------------------|-------|
| Database Password | AWS Secrets Manager | Quarterly | DevOps |
| API Keys (Stripe, etc.) | AWS Secrets Manager | Annually | DevOps |
| JWT Signing Key | AWS Secrets Manager | Semi-annually | DevOps |
| AWS Access Keys | AWS IAM | Quarterly | DevOps |
| SSL/TLS Certificates | AWS ACM | Auto-renewal | DevOps |
| Encryption Keys | AWS KMS | Annually | DevOps |

### Development Secrets

| Secret Type | Storage Location | Rotation Schedule | Owner |
|-------------|------------------|-------------------|-------|
| Local Database Password | .env.local (gitignored) | On team member change | DevOps |
| Development API Keys | .env.local (gitignored) | As needed | Developer |
| Test Service Credentials | .env.test (gitignored) | As needed | Developer |

### CI/CD Secrets

| Secret Type | Storage Location | Rotation Schedule | Owner |
|-------------|------------------|-------------------|-------|
| GitHub Secrets | GitHub Repository Settings | Quarterly | DevOps |
| AWS Deployment Keys | GitHub Secrets + IAM | Quarterly | DevOps |
| Docker Registry Tokens | GitHub Secrets | Quarterly | DevOps |

---

## AWS Secrets Manager Configuration

### Secret Structure

**Database Credentials:**
```json
{
  "username": "postgres",
  "password": "auto-generated-32-char-string",
  "host": "prequal-db.xxxxx.us-east-1.rds.amazonaws.com",
  "port": 5432,
  "dbname": "prequal_prod"
}
```

**Stripe API Keys:**
```json
{
  "STRIPE_SECRET_KEY": "sk_live_xxxxx",
  "STRIPE_PUBLISHABLE_KEY": "pk_live_xxxxx",
  "STRIPE_WEBHOOK_SECRET": "whsec_xxxxx"
}
```

**General API Secrets:**
```json
{
  "API_KEY_NAME": "value",
  "ANOTHER_API_KEY": "value"
}
```

### Terraform Configuration

Secrets are defined in `terraform/main.tf`:

```hcl
# AWS Secrets Manager for Stripe and API secrets
resource "aws_secretsmanager_secret" "stripe_secrets" {
  name        = "prequal/stripe-secrets"
  description = "Stripe API keys and webhook secrets for production"
  kms_key_id  = aws_kms_key.rds_encryption.arn

  tags = {
    Name = "prequal-stripe-secrets"
  }
}

resource "aws_secretsmanager_secret_version" "stripe_secrets" {
  secret_id = aws_secretsmanager_secret.stripe_secrets.id
  secret_string = jsonencode({
    STRIPE_SECRET_KEY     = "REPLACE_WITH_PRODUCTION_SECRET_KEY"
    STRIPE_PUBLISHABLE_KEY = "REPLACE_WITH_PRODUCTION_PUBLISHABLE_KEY"
    STRIPE_WEBHOOK_SECRET  = "REPLACE_WITH_WEBHOOK_SECRET"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
```

### Accessing Secrets in ECS

Secrets are injected as environment variables in the ECS task definition:

```json
{
  "secrets": [
    {
      "name": "DATABASE_URL",
      "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT_ID:parameter/prequal/database-url"
    },
    {
      "name": "STRIPE_SECRET_KEY",
      "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:prequal/stripe-secrets:STRIPE_SECRET_KEY::"
    }
  ]
}
```

---

## Secret Rotation Procedures

### Database Password Rotation

**Frequency:** Quarterly

**Steps:**

1. **Generate new password:**
```bash
openssl rand -base64 32
```

2. **Update in AWS Secrets Manager:**
```bash
aws secretsmanager update-secret \
  --secret-id prequal/database-credentials \
  --secret-string '{"username":"postgres","password":"NEW_PASSWORD"}'
```

3. **Update RDS password:**
```bash
aws rds modify-db-instance \
  --db-instance-identifier prequal-db \
  --master-user-password NEW_PASSWORD \
  --apply-immediately
```

4. **Restart ECS service:**
```bash
aws ecs update-service \
  --cluster prequal-cluster \
  --service prequal-service \
  --force-new-deployment
```

5. **Verify connectivity:**
```bash
# Test new credentials
curl https://prequal.yourcompany.com/api/health
```

6. **Document rotation:**
- Update rotation log
- Notify team of rotation completion

### API Key Rotation

**Frequency:** Annually or after team member departure

**Steps:**

1. **Generate new key in provider dashboard** (e.g., Stripe Dashboard)
2. **Update in AWS Secrets Manager**
3. **Deploy new version** (ECS picks up new secret)
4. **Verify functionality**
5. **Revoke old key** after 24-hour overlap period
6. **Document rotation**

### AWS Access Key Rotation

**Frequency:** Quarterly

**Steps:**

1. **Create new access key:**
```bash
aws iam create-access-key --user-name prequal-deployer
```

2. **Update GitHub secrets:**
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

3. **Test deployment** with new key

4. **Delete old access key:**
```bash
aws iam delete-access-key --access-key-id OLD_KEY_ID --user-name prequal-deployer
```

5. **Document rotation**

---

## GitHub Secrets Configuration

### Required Repository Secrets

Configure in: `GitHub Repository > Settings > Secrets and variables > Actions`

| Secret Name | Description | Rotation |
|-------------|-------------|----------|
| `AWS_ACCESS_KEY_ID` | AWS IAM access key for deployment | Quarterly |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key | Quarterly |
| `ALERT_EMAIL` | Email for deployment notifications | As needed |
| `SENTRY_DSN` | Sentry error tracking DSN | As needed |

### Setting GitHub Secrets

```bash
# Via GitHub CLI
gh secret set AWS_ACCESS_KEY_ID --body "AKIAIOSFODNN7EXAMPLE"
gh secret set AWS_SECRET_ACCESS_KEY --body "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

---

## Local Development Secrets

### .env.local Template

Create `.env.local` from `.env.example` (never commit .env.local):

```bash
# Copy template
cp .env.example .env.local

# Edit with local secrets
vim .env.local
```

### Example .env.example

```bash
# Database
DATABASE_URL=postgresql://postgres:local_password@localhost:5432/prequal_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=generate-with: openssl rand -hex 32
JWT_SECRET=generate-with: openssl rand -hex 32

# Stripe (Test Mode)
STRIPE_SECRET_KEY=sk_test_xxxxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxxxx

# Application
NODE_ENV=development
DEBUG=true
```

### Git Ignore Configuration

Ensure `.gitignore` includes:

```
# Environment files
.env
.env.local
.env.*.local

# Secrets
*.pem
*.key
secrets.json
credentials
```

---

## Access Control

### Who Has Access

| Role | Secrets Access |
|------|----------------|
| DevOps Engineer | All production secrets |
| CTO | All production secrets |
| Senior Engineers | Read-only production secrets |
| Developers | Development secrets only |

### IAM Policy for Secrets Access

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:prequal/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:UpdateSecret",
        "secretsmanager:RotateSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:prequal/*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:username": "prequal-deployer"
        }
      }
    }
  ]
}
```

---

## Audit and Compliance

### Audit Log Requirements

All secret access must be logged:
- Who accessed the secret
- When it was accessed
- From which IP/service
- What operation was performed

### CloudTrail Configuration

Enable CloudTrail logging for Secrets Manager:

```bash
aws cloudtrail create-trail \
  --name prequal-secrets-trail \
  --s3-bucket-name prequal-cloudtrail-logs \
  --include-global-service-events
```

### Quarterly Audit Checklist

- [ ] Review CloudTrail logs for unauthorized access
- [ ] Verify all secrets rotated on schedule
- [ ] Confirm access list is up to date
- [ ] Remove access for departed team members
- [ ] Test secret rotation procedures
- [ ] Update documentation if needed

---

## Emergency Procedures

### Compromised Secret

**If a secret is suspected to be compromised:**

1. **Immediately rotate the secret:**
   - Generate new credential
   - Update in Secrets Manager
   - Deploy new version

2. **Revoke old secret:**
   - Disable/delete old credential
   - Update all dependent systems

3. **Investigate:**
   - Review CloudTrail logs
   - Identify source of compromise
   - Document findings

4. **Notify:**
   - CTO immediately
   - Security team if customer data involved
   - Legal if breach confirmed

### Leaked GitHub Secret

GitHub automatically scans for leaked secrets. If detected:

1. **GitHub will revoke the key automatically**
2. **Rotate immediately:**
   - Create new credential
   - Update in all locations
3. **Review commit history** for how it was leaked
4. **Add to .gitignore** if not already excluded
5. **Enable branch protection** to prevent future leaks

---

## Best Practices

### Do's

- ✅ Use AWS Secrets Manager for production secrets
- ✅ Rotate secrets on schedule
- ✅ Use IAM roles instead of access keys when possible
- ✅ Enable CloudTrail logging
- ✅ Use `.env.example` templates
- ✅ Audit access quarterly
- ✅ Document all rotation procedures

### Don'ts

- ❌ Never commit secrets to Git
- ❌ Never share secrets via chat/email
- ❌ Never hardcode secrets in application code
- ❌ Never use production secrets in development
- ❌ Never skip rotation schedule
- ❌ Never disable audit logging

---

## Tools and Automation

### Secret Rotation Automation

**Implemented** in `terraform/secret_rotation.tf` + `terraform/secret_rotation/index.py`:

- A generic rotation Lambda (`prequal-secret-rotation`) runs the standard
  four-step contract and regenerates the keys named in the secret's
  `RotationKeys` tag.
- `aws_secretsmanager_secret_rotation.api_secrets` rotates the JWT `SECRET_KEY`
  automatically with `automatically_after_days = 90` and forces an ECS
  redeployment on completion.
- Provider-managed credentials (Stripe, OSHA, SMTP, encryption key, DB
  password, analytics key) follow the manual procedures in
  [SECRET_ROTATION_RUNBOOK.md](./SECRET_ROTATION_RUNBOOK.md).

```hcl
resource "aws_secretsmanager_secret_rotation" "api_secrets" {
  secret_id           = aws_secretsmanager_secret.api_secrets.id
  rotation_lambda_arn = aws_lambda_function.secret_rotation.arn

  rotation_rules {
    automatically_after_days = 90
  }
}
```

### Runtime secret loading

`prequal-platform/app/services/secrets_manager.py` provides a cached Secrets
Manager client that hydrates missing environment variables at application
startup (`SECRETS_MANAGER_ENABLED=true`). Existing environment variables — for
example those injected by the ECS task definition — always take precedence, so
the loader is safe in every environment.

### Pre-commit Hook for Secret Detection

Install gitleaks pre-commit hook:

```bash
# Install gitleaks
brew install gitleaks

# Add to .git/hooks/pre-commit
# #!/bin/bash
gitleaks protect --staged --verbose
```

The repository also ships a dependency-free guard that works everywhere:

```bash
git config core.hooksPath .githooks   # enables .githooks/pre-commit
python3 scripts/scan_secrets.py       # full-tree scan
python3 scripts/scan_secrets.py --staged
```

### CI/CD Secret Scanning

GitHub Actions workflow includes secret scanning:

```yaml
- name: Run gitleaks secrets scan
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Secret Inventory

### Current Production Secrets

| Secret Name | Location | Last Rotated | Next Rotation | Owner |
|-------------|----------|--------------|---------------|-------|
| Database Password | AWS Secrets Manager | [Date] | [Date] | DevOps |
| Stripe API Keys | AWS Secrets Manager | [Date] | [Date] | DevOps |
| JWT Signing Key | AWS Secrets Manager | [Date] | [Date] | DevOps |
| AWS Access Keys | GitHub Secrets + IAM | [Date] | [Date] | DevOps |
| SSL Certificate | AWS ACM | [Auto] | [Auto] | DevOps |

### Rotation Log Template

| Date | Secret | Rotated By | Method | Verified |
|------|--------|------------|--------|----------|
| YYYY-MM-DD | Database Password | Name | Manual/ Auto | Yes/No |

---

## Compliance Requirements

### SOC 2 Requirements

- ✅ Encryption at rest (KMS)
- ✅ Access logging (CloudTrail)
- ✅ Regular rotation (quarterly)
- ✅ Access control (IAM policies)
- ✅ Audit trail (rotation logs)

### Data Classification

| Data Type | Classification | Storage |
|-----------|----------------|---------|
| Database Passwords | Confidential | Secrets Manager |
| API Keys | Confidential | Secrets Manager |
| Encryption Keys | Highly Confidential | KMS |
| User Credentials | Highly Confidential | Encrypted in DB |

---

**Last Updated**: 2026-10-04
**Maintained By**: Backend Engineer
**Review Schedule**: Quarterly
**Next Review**: 2027-01-04