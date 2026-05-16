# Production Deployment Checklist - Prequal Platform

## Overview
This checklist ensures all prerequisites are met before deploying the Prequal compliance platform to production.

## Pre-Deployment Checklist

### 1. Infrastructure Prerequisites
- [ ] AWS account configured with necessary permissions
- [ ] Terraform >= 1.0 installed locally
- [ ] AWS CLI configured with production credentials
- [ ] Domain name configured in Route53 (if using custom domain)
- [ ] SSL/TLS certificate provisioned in AWS Certificate Manager

### 2. Terraform Configuration
- [ ] Copy `terraform.tfvars.production` to `terraform.tfvars`
- [ ] Set production AWS account ID
- [ ] Generate secure database password (min 16 chars, mixed case, numbers, symbols)
- [ ] Verify CIDR blocks don't conflict with existing VPCs
- [ ] Review and approve all resource configurations

### 3. GitHub Secrets Configuration
Configure the following secrets in GitHub repository settings:
- [ ] `AWS_ACCESS_KEY_ID` - Production AWS access key
- [ ] `AWS_SECRET_ACCESS_KEY` - Production AWS secret key
- [ ] `DOCKER_PASSWORD` - Docker Hub password (if using Docker Hub)

### 4. Database Setup
- [ ] RDS PostgreSQL instance type selected (db.t3.micro for starter)
- [ ] Database password stored in AWS Secrets Manager
- [ ] Backup retention policy configured (recommended: 7 days)
- [ ] Database encryption at rest enabled

### 5. Security Configuration
- [ ] IAM roles configured with least-privilege principle
- [ ] Security groups restrict access to necessary ports only
- [ ] VPC flow logs enabled for network monitoring
- [ ] AWS WAF configured for ALB (recommended)

### 6. Monitoring & Alerting
- [ ] CloudWatch Logs configured for application logs
- [ ] CloudWatch Alarms for CPU, memory, and error rates
- [ ] SNS topic created for alerts
- [ ] Health check endpoint (/health) verified

### 7. Backup & Recovery
- [ ] RDS automated backups enabled
- [ ] ElastiCache backup schedule configured
- [ ] Disaster recovery plan documented
- [ ] Data retention policies defined

## Deployment Steps

### Step 1: Initialize Terraform
```bash
cd terraform
terraform init
```

### Step 2: Validate Configuration
```bash
terraform validate
terraform plan -out=tfplan
```

### Step 3: Review Plan
- [ ] Review all resources to be created
- [ ] Verify resource counts and types
- [ ] Confirm no unintended deletions

### Step 4: Apply Infrastructure
```bash
terraform apply tfplan
```

### Step 5: Verify Deployment
```bash
# Check ECS service status
aws ecs describe-services --cluster prequal-cluster --services prequal-service

# Check ALB health
aws elbv2 describe-target-health --target-group-arn <tg-arn>

# Run verification script
./prequal-platform/scripts/verify-deployment.sh
```

### Step 6: Test Application
- [ ] Access application via ALB DNS name
- [ ] Verify health endpoint returns 200 OK
- [ ] Test database connectivity
- [ ] Test Redis connectivity
- [ ] Verify CloudWatch Logs are flowing

## Post-Deployment Verification

### Application Health
- [ ] Frontend loads successfully
- [ ] Backend API responds to requests
- [ ] Database queries execute correctly
- [ ] Cache operations work (Redis)
- [ ] File uploads work (if applicable)

### Monitoring
- [ ] CloudWatch Logs show application startup
- [ ] No critical errors in logs
- [ ] Memory usage within expected range
- [ ] CPU usage within expected range
- [ ] Response times acceptable

### Security
- [ ] HTTPS enforced (if SSL configured)
- [ ] Direct database access blocked
- [ ] Only necessary ports open
- [ ] IAM roles have minimal permissions

## Rollback Procedure

If deployment fails:

1. **Stop ECS Service Update**
```bash
aws ecs update-service --cluster prequal-cluster --service prequal-service --force-new-deployment
```

2. **Revert Task Definition**
```bash
# Get previous task definition
aws ecs list-task-definitions --family-prefix prequal-task --sort DESC | jq '.taskArns[-2]'

# Rollback to previous version
aws ecs update-service --cluster prequal-cluster --service prequal-service --task-definition <previous-task-def>
```

3. **Restore Database** (if needed)
```bash
# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot --db-instance-identifier prequal-db-restore --db-snapshot-identifier <snapshot-id>
```

## Contact Information

- **DevOps Engineer**: 9eaad31d-6a31-4b0c-9117-1c781f4f80f9
- **CTO**: cea61f97-aa0b-43e3-8595-f13cd765171d

## Version History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-05-14 | 1.0 | Initial production checklist | DevOps Engineer |
