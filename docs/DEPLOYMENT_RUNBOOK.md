# Deployment Runbook - Prequal Platform

## Overview

This runbook provides step-by-step instructions for deploying the Prequal Platform to production. It includes pre-deployment checks, deployment steps, verification procedures, and rollback instructions.

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-25 | DevOps Engineer | Initial runbook |

---

## Pre-Deployment Checklist

### 1. Verify Infrastructure

```bash
# Check Terraform state
cd terraform
terraform init
terraform plan -out=tfplan

# Review planned changes
terraform show tfplan
```

- [ ] No unexpected resource deletions
- [ ] Database configuration unchanged (unless intentional)
- [ ] ECS task definition version updated
- [ ] ECR repositories exist

### 2. Verify Secrets

Ensure all required GitHub secrets are configured:

- [ ] `AWS_ACCESS_KEY_ID` - Production AWS access key
- [ ] `AWS_SECRET_ACCESS_KEY` - Production AWS secret key
- [ ] `ALERT_EMAIL` - Email for notifications
- [ ] `SENTRY_DSN` - Sentry error tracking DSN (if enabled)

### 3. Database Backup (Pre-Deployment)

```bash
# Create backup before deployment
aws rds create-db-snapshot \
  --db-instance-identifier prequal-db \
  --db-snapshot-identifier prequal-db-snapshot-$(date +%Y%m%d-%H%M%S)
```

- [ ] Database snapshot created
- [ ] Snapshot verified in AWS Console

### 4. Notify Team

- [ ] Post deployment notification in team channel
- [ ] Confirm deployment window is clear
- [ ] Verify no critical user operations in progress

---

## Deployment Steps

### Step 1: Trigger Production Deployment

#### Option A: Automated (Recommended)

```bash
# Tag release commit
git tag -a v1.0.0 -m "Production release"
git push origin v1.0.0
```

The GitHub Actions workflow will automatically deploy.

#### Option B: Manual Deployment

```bash
# From GitHub UI:
# 1. Go to Actions > Production Deployment
# 2. Click "Run workflow"
# 3. Select version and environment
# 4. Click "Run workflow"
```

### Step 2: Monitor Deployment

```bash
# Watch GitHub Actions progress
# GitHub > Actions > Production Deployment

# Monitor ECS service
aws ecs describe-services \
  --cluster prequal-cluster \
  --services prequal-service \
  --region us-east-1

# Check deployment status
aws ecs list-deployments \
  --cluster prequal-cluster \
  --service prequal-service \
  --region us-east-1
```

- [ ] Backend service deploying
- [ ] Frontend service deploying
- [ ] No deployment failures

### Step 3: Verify Health Checks

```bash
# Backend health
curl -f https://prequal.yourcompany.com/api/health

# Frontend health
curl -f https://prequal.yourcompany.com/

# Expected: 200 OK with healthy status
```

- [ ] Backend responds with 200 OK
- [ ] Frontend loads successfully
- [ ] No console errors

### Step 4: Run Smoke Tests

```bash
# Test authentication
curl -X POST https://prequal.yourcompany.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test"}'

# Test database connectivity
curl -f https://prequal.yourcompany.com/api/health/detailed

# Expected: All dependencies healthy
```

- [ ] Authentication works
- [ ] Database connection successful
- [ ] Redis connection successful
- [ ] API endpoints respond

---

## Post-Deployment Verification

### Application Health

- [ ] Dashboard loads without errors
- [ ] Subcontractor list displays
- [ ] Compliance reports generate
- [ ] Alerts function correctly
- [ ] File uploads work (if applicable)

### Monitoring Verification

```bash
# Check CloudWatch Logs
aws logs tail /ecs/prequal-app --limit 50

# Verify metrics are flowing
aws cloudwatch list-metrics \
  --namespace ECS \
  --metric-name CPUUtilization
```

- [ ] Logs appearing in CloudWatch
- [ ] Metrics visible in CloudWatch
- [ ] No critical errors in logs
- [ ] Uptime monitoring active

### Database Verification

```bash
# Check database connections
aws rds describe-db-instances \
  --db-instance-identifier prequal-db

# Verify backup status
aws rds describe-db-snapshots \
  --db-instance-identifier prequal-db \
  --sort-by snapshot_create_time \
  --sort-order descending \
  --max-items 1
```

- [ ] Database instance healthy
- [ ] Automated backups enabled
- [ ] Latest snapshot successful

---

## Rollback Procedure

### Immediate Rollback (Critical Issues Only)

If deployment causes critical failures:

#### Step 1: Stop Deployment

```bash
# Cancel ongoing deployment
aws ecs update-service \
  --cluster prequal-cluster \
  --service prequal-service \
  --force-new-deployment \
  --region us-east-1
```

#### Step 2: Rollback to Previous Version

```bash
# Get previous task definition
PREVIOUS_TASK=$(aws ecs list-task-definitions \
  --family-prefix prequal-task \
  --sort DESC \
  --max-items 2 \
  --query 'taskArns[-1]' \
  --output text)

# Rollback
aws ecs update-service \
  --cluster prequal-cluster \
  --service prequal-service \
  --task-definition "$PREVIOUS_TASK" \
  --region us-east-1
```

#### Step 3: Restore Database (If Needed)

```bash
# Restore from pre-deployment snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier prequal-db-restored \
  --db-snapshot-identifier prequal-db-snapshot-YYYYMMDD-HHMMSS
```

#### Step 4: Notify Team

- [ ] Post rollback notification
- [ ] Document reason for rollback
- [ ] Schedule post-mortem

---

## Troubleshooting

### Deployment Fails - ECS Service

**Symptom**: Service fails to reach steady state

```bash
# Check service events
aws ecs describe-services \
  --cluster prequal-cluster \
  --services prequal-service \
  --query 'services[0].events' \
  --region us-east-1

# Check task definition
aws ecs describe-task-definition \
  --task-definition prequal-task
```

**Solution**: Verify task definition, check image exists in ECR

### Deployment Fails - Health Check

**Symptom**: Health checks fail after deployment

```bash
# Check container logs
aws logs tail /ecs/prequal-app --filter-pattern "ERROR"

# Test health endpoint directly
curl -v https://prequal.yourcompany.com/api/health
```

**Solution**: Check application logs, verify environment variables

### Database Connection Issues

**Symptom**: Application cannot connect to database

```bash
# Check security group
aws ec2 describe-security-groups \
  --group-ids sg-xxxxx \
  --query 'SecurityGroups[0].IpPermissions'

# Test connectivity
aws rds describe-db-instances \
  --db-instance-identifier prequal-db \
  --query 'DBInstances[0].Endpoint'
```

**Solution**: Verify security group allows ECS, check DATABASE_URL

---

## Emergency Contacts

| Role | Contact |
|------|---------|
| DevOps Engineer | @devops |
| CTO | @cto |
| On-Call Engineer | @oncall |

---

## Appendix: Environment Variables

### Required Variables

```bash
# Security
SECRET_KEY=<generated>
POSTGRES_PASSWORD=<strong-password>

# Domain
DOMAIN=prequal.yourcompany.com
TRAEFIK_ACME_EMAIL=admin@yourcompany.com

# Database
DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/prequal_prod

# Redis
REDIS_URL=redis://redis:6379/0

# Application
APP_NAME="Prequal Platform"
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
ALLOWED_ORIGINS=https://prequal.yourcompany.com
```

### Optional Variables

```bash
# Email
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=noreply@yourcompany.com
SMTP_PASSWORD=<password>
EMAIL_FROM=noreply@yourcompany.com

# Monitoring
ALERT_EMAIL=admin@yourcompany.com
SENTRY_DSN=<sentry-dsn>
```

---

**Last Updated**: 2026-05-25
**Maintained By**: DevOps Engineer
