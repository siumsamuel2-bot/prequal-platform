# Production Infrastructure Setup Guide

## Overview

This guide covers the complete setup of production infrastructure for the Prequal Platform, including:
- Stripe webhook endpoint deployment
- SSL/TLS certificate configuration
- Monitoring and alerting
- CI/CD pipeline setup
- Secrets management
- Database backup strategy
- DDoS protection

## Prerequisites

1. AWS account with administrative access
2. Terraform >= 1.0 installed
3. AWS CLI configured with production credentials
4. Domain name registered (for SSL certificate)
5. GitHub repository with CI/CD workflows

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                               │
│  ┌─────────────┐                                               │
│  │  CloudFront │ (optional CDN layer)                          │
│  └──────┬──────┘                                               │
│         │                                                       │
│  ┌──────▼──────────────────────────────────────────────┐       │
│  │         WAF (DDoS Protection + Rate Limiting)       │       │
│  └──────┬──────────────────────────────────────────────┘       │
│         │                                                       │
│  ┌──────▼──────┐                                               │
│  │     ALB     │ (Application Load Balancer - HTTPS)           │
│  │  + ACM Cert │ (SSL/TLS termination)                         │
│  └──────┬──────┘                                               │
│         │                                                       │
│  ┌──────▼──────────────────────────────────────────────┐       │
│  │              ECS Cluster (Fargate)                   │       │
│  │  ┌─────────────────────────────────────────────┐    │       │
│  │  │  Task: prequal-app (2+ replicas)            │    │       │
│  │  │  - Stripe webhook endpoint                  │    │       │
│  │  │  - API services                             │    │       │
│  │  └─────────────────────────────────────────────┘    │       │
│  └──────────────────────────────────────────────────────┘       │
│         │                                                       │
│  ┌──────▼──────┐     ┌──────────────┐                          │
│  │  RDS PostgreSQL│   │ ElastiCache  │                          │
│  │  (encrypted) │     │   (Redis)    │                          │
│  └──────────────┘     └──────────────┘                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              Secrets Manager                         │      │
│  │  - Stripe API keys                                   │      │
│  │  - Stripe webhook secrets                            │      │
│  │  - Database credentials                              │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              CloudWatch                              │      │
│  │  - Metrics & Alarms                                  │      │
│  │  - Log aggregation                                   │      │
│  │  - Dashboard                                         │      │
│  │  - SNS notifications                                 │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

## Step 1: Configure Terraform Variables

1. Copy the example variables file:
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

2. Edit `terraform.tfvars` with production values:
```hcl
# AWS Account ID - Your production AWS account ID
aws_account_id = "123456789012"

# Database password - Generate a strong, unique password
# Recommended: Use AWS Secrets Manager or AWS Password Manager
db_password = "YourSecurePassword123!"

# AWS Region
aws_region = "us-east-1"

# VPC CIDR - Ensure no overlap with existing VPCs
vpc_cidr = "10.0.0.0/16"

# Subnet CIDRs
public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.3.0/24", "10.0.4.0/24"]

# Domain name for SSL certificate (must be validated in Route53 or DNS)
domain_name = "prequal.yourdomain.com"

# Alert email for production monitoring
alert_email = "devops@yourdomain.com"
```

**Security Note:** Never commit `terraform.tfvars` with real passwords. Use environment variables or AWS Secrets Manager.

## Step 2: Configure GitHub Secrets

Set up the following secrets in your GitHub repository:

1. Navigate to: `Settings > Secrets and variables > Actions`

2. Add repository secrets:
```
AWS_ACCESS_KEY_ID        = Your AWS access key
AWS_SECRET_ACCESS_KEY    = Your AWS secret key
ALERT_EMAIL              = devops@yourdomain.com
```

3. For production environment protection:
   - Go to `Settings > Environments > production`
   - Add required reviewers for deployment approval

## Step 3: Initialize and Deploy Infrastructure

### 3.1 Initialize Terraform
```bash
cd terraform
terraform init
```

### 3.2 Validate Configuration
```bash
terraform validate
terraform plan -out=tfplan
```

### 3.3 Review the Plan
Carefully review:
- All resources to be created
- Security group rules
- IAM policies
- Network configuration

### 3.4 Apply Infrastructure
```bash
terraform apply tfplan
```

This will create:
- VPC with public/private subnets
- Application Load Balancer with HTTPS listener
- ECS cluster and service
- RDS PostgreSQL instance
- ElastiCache Redis cluster
- Secrets Manager secrets
- CloudWatch alarms and dashboard
- SNS topic for alerts
- WAF for DDoS protection

**Deployment Time:** 15-20 minutes

## Step 4: Configure SSL Certificate

1. After Terraform apply, check ACM certificate status:
```bash
aws acm describe-certificate \
  --certificate-arn <arn-from-terraform-output>
```

2. Validate the domain:
   - If using Route53: Add CNAME record as shown in ACM console
   - If using external DNS: Add CNAME record provided by ACM

3. Wait for validation (typically 5-15 minutes)

## Step 5: Configure Stripe Webhook

### 5.1 Generate Webhook Secret
1. Log into Stripe Dashboard
2. Navigate to: `Developers > Webhooks`
3. Add endpoint: `https://<your-alb-dns-name>/api/webhooks/stripe`
4. Copy the signing secret

### 5.2 Update Secrets Manager
```bash
aws secretsmanager update-secret \
  --secret-id prequal/stripe-secrets \
  --secret-string '{
    "STRIPE_SECRET_KEY": "sk_live_xxx",
    "STRIPE_PUBLISHABLE_KEY": "pk_live_xxx",
    "STRIPE_WEBHOOK_SECRET": "whsec_xxx"
  }'
```

### 5.3 Deploy Updated Configuration
```bash
aws ecs update-service \
  --cluster prequal-cluster \
  --service prequal-service \
  --force-new-deployment
```

## Step 6: Verify Deployment

### 6.1 Check ECS Service
```bash
aws ecs describe-services \
  --cluster prequal-cluster \
  --services prequal-service
```

### 6.2 Check ALB Health
```bash
aws elbv2 describe-target-health \
  --target-group-arn <tg-arn>
```

### 6.3 Test Stripe Webhook
```bash
# Send test event from Stripe Dashboard
# Or use Stripe CLI:
stripe trigger payment_intent.created
```

### 6.4 Verify HTTPS
```bash
curl -I https://<your-alb-dns-name>/health
```

## Step 7: Configure Monitoring

### 7.1 Access CloudWatch Dashboard
1. Navigate to: `CloudWatch > Dashboards`
2. Open `prequal-production`

### 7.2 Confirm SNS Subscription
1. Check email for SNS subscription confirmation
2. Click "Confirm subscription"
3. Note the subscription ARN for records

### 7.3 Test Alerts
Trigger a test alarm:
```bash
aws cloudwatch set-alarm-state \
  --alarm-name prequal-high-error-rate \
  --state-value ALARM \
  --state-reason "Testing alert system"
```

You should receive an email notification.

## Step 8: Database Backup Verification

### 8.1 Verify Automated Backups
```bash
aws rds describe-db-instances \
  --db-instance-identifier prequal-db \
  --query 'DBInstances[0].{BackupRetention:BackupRetentionPeriod,Window:PreferredBackupWindow}'
```

### 8.2 Manual Snapshot (Before Major Changes)
```bash
aws rds create-db-snapshot \
  --db-instance-identifier prequal-db \
  --db-snapshot-identifier prequal-db-pre-deploy-$(date +%Y%m%d)
```

### 8.3 Backup Retention
- Automated backups: 7 days (configured in Terraform)
- Manual snapshots: Retained until explicitly deleted
- Point-in-time recovery: Enabled

## Step 9: CI/CD Pipeline Verification

### 9.1 Test Deployment Workflow
1. Push a change to `main` branch
2. Monitor GitHub Actions: `Actions > Production Deployment`
3. Verify stages:
   - validate-infrastructure
   - test
   - build-and-push
   - deploy-infrastructure
   - deploy-ecs
   - health-check

### 9.2 Rollback Procedure
If deployment fails:
```bash
# Get previous task definition
aws ecs list-task-definitions \
  --family-prefix prequal-task \
  --sort DESC \
  --max-results 2

# Rollback
aws ecs update-service \
  --cluster prequal-cluster \
  --service prequal-service \
  --task-definition <previous-task-def> \
  --force-new-deployment
```

## Security Checklist

- [ ] Security groups allow only necessary ports (80, 443)
- [ ] RDS instance not publicly accessible
- [ ] All secrets stored in Secrets Manager
- [ ] IAM roles follow least-privilege principle
- [ ] WAF rules active for DDoS protection
- [ ] HTTPS enforced with HTTP redirect
- [ ] Database encryption at rest enabled
- [ ] VPC flow logs enabled (optional)
- [ ] SSL certificate valid and not expiring soon

## Monitoring Alerts

| Alert | Threshold | Action |
|-------|-----------|--------|
| High Error Rate | 5xx errors > 10 in 5 min | Investigate application logs |
| High Latency | p95 > 2s for 5 min | Review slow queries, scale up |
| ECS High CPU | CPU > 80% for 5 min | Scale service or optimize |
| ECS High Memory | Memory > 80% for 5 min | Check for memory leaks |
| RDS High CPU | CPU > 80% for 5 min | Optimize queries, scale RDS |
| RDS Low Storage | Free space < 5GB | Expand storage |
| Unhealthy Hosts | Any unhealthy targets | Investigate ECS tasks |
| Stripe Webhook Failures | > 5 failures in 5 min | Check webhook signature validation |

## Cost Optimization

1. **Right-size resources:**
   - ECS tasks: Start with 256 CPU / 512 MB
   - RDS: db.t3.micro for starter, scale as needed
   - Redis: cache.t3.micro

2. **Enable cost allocation tags:**
   - All resources tagged with `Name` and environment

3. **Set up AWS Budgets:**
   - Create budget alerts at 50%, 80%, 100% of monthly limit

## Troubleshooting

### SSL Certificate Not Validating
- Verify DNS CNAME record is correct
- Wait up to 30 minutes for DNS propagation
- Check ACM console for validation status

### ECS Tasks Not Starting
- Check task definition IAM role permissions
- Verify ECR repository policy allows ECS pull
- Review CloudWatch Logs for startup errors

### Database Connection Failures
- Verify security group allows ECS task access
- Check DATABASE_URL secret value
- Ensure RDS instance is in available state

### Stripe Webhook Signature Validation Fails
- Verify STRIPE_WEBHOOK_SECRET matches Stripe Dashboard
- Check webhook endpoint receives raw body (not parsed JSON)
- Ensure signature header is `Stripe-Signature`

## Next Steps

1. Set up staging environment for testing
2. Configure horizontal pod autoscaling
3. Implement blue-green deployments
4. Add canary deployment support
5. Set up log aggregation with centralized logging
6. Create runbooks for each alert type

## Support

For issues or questions:
- DevOps Engineer: 9eaad31d-6a31-4b0c-9117-1c781f4f80f9
- CTO: cea61f97-aa0b-43e3-8595-f13cd765171d

## Version History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-06-08 | 1.1 | Added CloudWatch alarms, SNS alerts, comprehensive monitoring | DevOps Engineer |
| 2026-05-14 | 1.0 | Initial production setup guide | DevOps Engineer |