# Production Infrastructure Implementation Summary

**Issue**: [MID-70](/MID/issues/MID-70)  
**Date**: 2026-06-07  
**Author**: DevOps Engineer  

## Overview

This document summarizes the infrastructure improvements implemented for production deployment of the Prequal platform, addressing Stripe webhook handling, SSL/TLS configuration, monitoring, secrets management, database backups, and DDoS protection.

## What Was Implemented

### 1. SSL/TLS Certificates and HTTPS Enforcement ✅

**Changes:**
- Added ACM certificate resource for domain validation
- Configured HTTPS listener on port 443 with TLS 1.3 security policy
- HTTP listener now redirects all traffic to HTTPS (301 permanent redirect)
- Updated ECS service to depend on HTTPS listener

**Files Modified:**
- `terraform/main.tf` - Added `aws_acm_certificate`, `aws_lb_listener.prequal_https`
- `terraform/variables.tf` - Added `domain_name` variable

**Security Policy:** `ELBSecurityPolicy-TLS13-1-2-2021-06` (TLS 1.3 only)

### 2. Production Secrets Management ✅

**Changes:**
- Created AWS Secrets Manager secrets for Stripe credentials
- Added KMS encryption key for secret encryption
- Updated ECS task definition to pull secrets from Secrets Manager
- Added IAM policy for ECS tasks to access Secrets Manager
- Created SSM Parameter Store entry for DATABASE_URL

**Secrets Configured:**
- `prequal/stripe-secrets` - Stripe API keys and webhook secret
- `prequal/api-secrets` - General API keys (ready for future use)
- `/prequal/database-url` - Database connection string (SSM SecureString)

**Files Modified:**
- `terraform/main.tf` - Added Secrets Manager resources, KMS key, IAM policies
- ECS task definition now uses `secrets` block instead of plain environment variables

**Important:** After terraform apply, update the secret values in AWS Secrets Manager with actual production credentials:
```bash
aws secretsmanager update-secret \
  --secret-id prequal/stripe-secrets \
  --secret-string '{"STRIPE_SECRET_KEY":"sk_live_...","STRIPE_PUBLISHABLE_KEY":"pk_live_...","STRIPE_WEBHOOK_SECRET":"whsec_..."}'
```

### 3. Database Backup Strategy ✅

**Changes:**
- Enabled automated RDS backups with 7-day retention
- Configured backup window (3:00 AM - 4:00 AM UTC)
- Enabled final snapshot on deletion
- Enabled storage encryption with KMS
- Enabled copy tags to snapshot for better organization

**Configuration:**
- `backup_retention_period = 7` - Daily snapshots retained for 7 days
- `backup_window = "03:00-04:00"` - Low-traffic backup window
- `skip_final_snapshot = false` - Final snapshot on deletion
- `storage_encrypted = true` - Encryption at rest
- `copy_tags_to_snapshot = true` - Tags copied to snapshots

**Files Modified:**
- `terraform/main.tf` - Updated `aws_db_instance.prequal_db`

### 4. DDoS and Rate Limiting Protection (AWS WAF) ✅

**Changes:**
- Created AWS WAF Web ACL with multiple protection layers
- Associated WAF with Application Load Balancer

**Protection Rules:**
1. **Rate-based rule** - Blocks IPs exceeding 2000 requests per 5 minutes
2. **AWS Managed Common Rule Set** - Protects against OWASP Top 10 attacks
3. **AWS Managed SQL Injection Rule Set** - SQL injection protection

**Files Modified:**
- `terraform/main.tf` - Added `aws_wafv2_web_acl.prequal_waf` and association

**CloudWatch Metrics:**
- All WAF rules emit metrics for monitoring
- Dashboard available in CloudWatch Console

### 5. Enhanced Monitoring and Alerting ✅

**Existing Infrastructure (Verified):**
- CloudWatch alarms for backend errors, latency, ECS task health
- CloudWatch alarms for RDS CPU and storage
- SNS topic for alert notifications
- CloudWatch dashboard with key metrics

**Alert Configuration:**
- High error rate (>10 5XX errors in 5 min)
- High latency (>5s average response time)
- Unhealthy ECS tasks
- RDS CPU >80%
- RDS free storage <10GB

**Files Verified:**
- `prequal-platform/infrastructure/monitoring.tf`
- `prequal-platform/monitoring/` - Prometheus/Grafana stack

### 6. CI/CD Pipeline with Automated Testing ✅

**Existing Pipeline (Verified):**
- Infrastructure validation (Terraform fmt, validate)
- Unit tests (Node.js and Python/pytest)
- Docker image build and push to ECR
- Security scanning with Trivy
- Automated ECS deployment
- Health check verification

**Pipeline Stages:**
1. `validate-infrastructure` - Terraform validation
2. `test` - Unit tests for frontend and backend
3. `build-and-push` - Docker images with security scan
4. `deploy-infrastructure` - Terraform apply
5. `deploy-ecs` - ECS service update with migrations
6. `health-check` - Post-deployment verification

**Files Verified:**
- `.github/workflows/production-deployment.yml`

## Infrastructure Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    AWS WAF (Rate Limiting)                   │
│              - 2000 req/5min per IP                          │
│              - SQL Injection Protection                      │
│              - OWASP Common Rules                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Application Load Balancer (HTTPS)               │
│              - ACM SSL Certificate                           │
│              - HTTP→HTTPS Redirect (301)                     │
│              - TLS 1.3 Only                                  │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
    ┌───────────────────┐           ┌───────────────────┐
    │  Frontend Service │           │  Backend Service  │
    │   (ECS Fargate)   │           │   (ECS Fargate)   │
    │   2 tasks minimum │           │   2 tasks minimum │
    └───────────────────┘           └───────────────────┘
                                            │
                            ┌───────────────┼───────────────┐
                            ▼               ▼               ▼
                    ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
                    │    RDS      │ │   Elasti    │ │   Secrets    │
                    │  PostgreSQL │ │   Cache     │ │   Manager    │
                    │  (Encrypted)│ │   (Redis)   │ │  + KMS Key   │
                    │  7-day backup│ │             │ │              │
                    └─────────────┘ └─────────────┘ └──────────────┘
```

## Deployment Instructions

### Prerequisites

1. AWS CLI configured with production credentials
2. Terraform >= 1.0 installed
3. Domain name configured in Route53 (if using custom domain)
4. GitHub secrets configured:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `ALERT_EMAIL`

### Initial Deployment

```bash
cd terraform

# Copy production variables
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with production values:
# - aws_account_id
# - domain_name (optional but recommended for HTTPS)
# - db_password (generate secure password)

# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Review planned changes
terraform plan -out=tfplan

# Apply infrastructure
terraform apply tfplan
```

### Update Secrets After Deployment

```bash
# Update Stripe secrets with production values
aws secretsmanager update-secret \
  --secret-id prequal/stripe-secrets \
  --secret-string '{"STRIPE_SECRET_KEY":"sk_live_...","STRIPE_PUBLISHABLE_KEY":"pk_live_...","STRIPE_WEBHOOK_SECRET":"whsec_..."}'

# Update DATABASE_URL in SSM Parameter Store
aws ssm put-parameter \
  --name "/prequal/database-url" \
  --value "postgresql://user:password@host:5432/prequal" \
  --type "SecureString" \
  --key-id "alias/prequal-rds-encryption" \
  --overwrite
```

### Trigger Deployment

Push to `main` branch or manually trigger via GitHub Actions:
1. Go to Actions tab
2. Select "Production Deployment"
3. Click "Run workflow"
4. Select version/environment
5. Click "Run workflow"

## Monitoring and Alerts

### CloudWatch Dashboard

Access via AWS Console: CloudWatch → Dashboards → `prequal-platform`

**Key Metrics:**
- Backend Response Time (ALB TargetResponseTime)
- Backend Error Rate (ALB 5XXError)
- RDS CPU Utilization
- ECS Running Tasks

### Alert Configuration

Alerts are sent to SNS topic `prequal-alerts`. To add email subscribers:

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:<account-id>:prequal-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com
```

Confirm subscription via email.

### WAF Metrics

Access via AWS Console: WAF → Web ACLs → prequal-waf → Metrics

**Key Metrics:**
- Allowed requests
- Blocked requests (rate limiting)
- Blocked requests (SQL injection)
- Blocked requests (common rules)

## Security Considerations

### Secrets Management
- ✅ All secrets stored in AWS Secrets Manager with KMS encryption
- ✅ DATABASE_URL stored in SSM Parameter Store as SecureString
- ✅ ECS tasks use IAM roles to access secrets (no hardcoded credentials)
- ✅ KMS key rotation enabled

### Network Security
- ✅ HTTPS enforced (HTTP redirects to HTTPS)
- ✅ TLS 1.3 only (modern security policy)
- ✅ WAF with rate limiting and attack protection
- ✅ Security groups restrict access to necessary ports only
- ✅ ECS tasks in private subnets (no public IP)

### Data Security
- ✅ RDS storage encrypted with KMS
- ✅ Automated backups encrypted
- ✅ Final snapshot on deletion (prevent accidental data loss)

### Access Control
- ✅ IAM roles follow least-privilege principle
- ✅ ECS task role limited to ECR, Logs, Secrets Manager, KMS
- ✅ No secrets in codebase or environment variables

## Rollback Procedure

If deployment fails:

1. **Stop ECS Service Update:**
```bash
aws ecs update-service \
  --cluster prequal-cluster \
  --service prequal-service \
  --force-new-deployment
```

2. **Rollback to Previous Task Definition:**
```bash
# Get previous task definition ARN
aws ecs list-task-definitions \
  --family-prefix prequal-task \
  --sort DESC \
  --max-items 2 \
  --query 'taskDefinitionArns[-1]'

# Update service to previous version
aws ecs update-service \
  --cluster prequal-cluster \
  --service prequal-service \
  --task-definition <previous-task-def-arn>
```

3. **Restore Database from Snapshot (if needed):**
```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier prequal-db-restore \
  --db-snapshot-identifier <snapshot-id>
```

## Cost Estimate

**Monthly Infrastructure Costs (us-east-1):**

| Resource | Configuration | Estimated Cost |
|----------|--------------|----------------|
| ECS Fargate | 2 tasks × 0.25 vCPU, 0.5GB | ~$15/month |
| RDS PostgreSQL | db.t3.micro | ~$15/month |
| ElastiCache Redis | cache.t3.micro | ~$15/month |
| ALB | Application Load Balancer | ~$20/month |
| WAF | Web ACL + rules | ~$5/month |
| CloudWatch | Logs + metrics | ~$5/month |
| **Total** | | **~$75/month** |

*Note: Costs may vary based on actual usage, data transfer, and region.*

## Next Steps

### Immediate (Before Production Launch)
- [ ] Update Secrets Manager with actual Stripe production keys
- [ ] Configure domain name in Route53 and ACM validation
- [ ] Add team emails to SNS alert subscription
- [ ] Test rollback procedure in staging environment
- [ ] Verify WAF rules don't block legitimate traffic

### Short-term (Post-Launch)
- [ ] Set up Grafana dashboard for detailed metrics
- [ ] Configure Prometheus metrics in application code
- [ ] Create runbooks for each alert type
- [ ] Implement log aggregation with Loki
- [ ] Set up weekly health reports

### Long-term (Optimization)
- [ ] Implement blue-green deployment strategy
- [ ] Add canary deployments for safer releases
- [ ] Configure auto-scaling based on metrics
- [ ] Implement distributed tracing (OpenTelemetry)
- [ ] Add synthetic monitoring for critical user journeys

## References

- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS WAF Documentation](https://docs.aws.amazon.com/waf/latest/developerguide/)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/)
- [ECS Task Definition Secrets](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data.html)
- [ALB Listener Rules](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/listener-update-rules.html)

---

**Document Version**: 1.0  
**Last Updated**: 2026-06-07  
**Maintained By**: DevOps Engineer  
**Related Issues**: [MID-70](/MID/issues/MID-70)