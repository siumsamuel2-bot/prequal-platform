# Prequal Platform - Production Infrastructure Setup Guide

## Overview

This guide covers the complete infrastructure setup for deploying the Prequal Platform to AWS using Terraform and Amazon ECS (Fargate).

## Architecture

```
                                    ┌─────────────────┐
                                    │  Route 53 DNS   │
                                    │  (Domain)       │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │   ACM SSL Cert  │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                              ┌─────│  ALB (HTTPS)    │─────┐
                              │     └─────────────────┘     │
                              │                             │
                    ┌─────────▼─────────┐       ┌──────────▼──────────┐
                    │  Frontend Service │       │  Backend Service    │
                    │  (ECS Fargate x2) │       │  (ECS Fargate x2)   │
                    │  Port: 80         │       │  Port: 8000         │
                    └─────────┬─────────┘       └──────────┬──────────┘
                              │                             │
                              │         ┌───────────────────┘
                              │         │
                    ┌─────────▼─────────▼──────────┐
                    │      VPC (Private Subnet)    │
                    │  ┌────────────┐  ┌─────────┐│
                    │  │   RDS      │  │ Elasti- ││
                    │  │ PostgreSQL │  │ Cache   ││
                    │  │            │  │ Redis   ││
                    │  └────────────┘  └─────────┘│
                    └─────────────────────────────┘
```

## Prerequisites

### Software Requirements

- **Terraform**: >= 1.5.0
- **AWS CLI**: >= 2.0
- **Docker**: >= 24.0
- **Git**: Latest version

### AWS Requirements

- AWS Account with admin access
- Domain registered in Route53 (or ability to update DNS)
- AWS credentials configured

### Configuration Required

1. **Domain**: `prequal.yourcompany.com` (or your domain)
2. **Email**: For SSL certificate notifications
3. **Alert Email**: For CloudWatch alarms

## Quick Start

### 1. Clone and Navigate

```bash
cd prequal-platform/infrastructure
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Create Terraform Variables

Create a `terraform.tfvars` file:

```hcl
aws_region    = "us-east-1"
environment   = "production"
domain_name   = "prequal.yourcompany.com"
alert_email   = "devops@yourcompany.com"
```

### 4. Plan and Apply

```bash
# Review the plan
terraform plan -out=tfplan

# Apply infrastructure
terraform apply tfplan
```

### 5. Build and Push Docker Images

```bash
# Get ECR repository URLs from Terraform output
ECR_BACKEND=$(terraform output -raw backend_ecr_repository_url)
ECR_FRONTEND=$(terraform output -raw frontend_ecr_repository_url)

# Build and push images
../scripts/deploy.sh build
```

### 6. Deploy to ECS

```bash
# Deploy latest version
../scripts/deploy.sh deploy latest
```

## Infrastructure Components

### Compute (AWS ECS Fargate)

| Component | Instance Type | Count | CPU | Memory |
|-----------|--------------|-------|-----|--------|
| Backend | Fargate | 2 | 1 vCPU | 2 GB |
| Frontend | Fargate | 2 | 0.5 vCPU | 1 GB |

### Database (RDS PostgreSQL)

| Setting | Value |
|---------|-------|
| Engine | PostgreSQL 15 |
| Instance | db.t3.medium |
| Storage | 100 GB GP3 |
| Multi-AZ | Yes |
| Backup Retention | 30 days |

### Cache (ElastiCache Redis)

| Setting | Value |
|---------|-------|
| Engine | Redis 7.0 |
| Instance | cache.t3.medium |
| Nodes | 1 |

### Load Balancer (ALB)

| Setting | Value |
|---------|-------|
| Type | Application Load Balancer |
| HTTPS | Yes (TLS 1.2) |
| SSL | ACM Certificate |
| Health Checks | Enabled |

## Deployment Commands

### Full Deployment

```bash
# Build images and deploy
./scripts/deploy.sh deploy v1.0.0

# With health check endpoint
./scripts/deploy.sh deploy v1.0.0 --endpoint https://prequal.yourcompany.com
```

### Rollback

```bash
# Rollback to previous version
./scripts/deploy.sh rollback v0.9.9
```

### Health Checks

```bash
# Check deployment health
./scripts/deploy.sh health https://prequal.yourcompany.com
```

### Status

```bash
# View current deployment status
./scripts/deploy.sh status
```

## Monitoring

### CloudWatch Dashboard

Access the pre-built dashboard in AWS Console:
- Navigate to CloudWatch > Dashboards
- Select `prequal-platform`

### Alarms Configured

| Alarm | Threshold | Action |
|-------|-----------|--------|
| Backend Error Rate | > 10 errors (5 min) | Email alert |
| Backend Latency | > 5s average (5 min) | Email alert |
| Unhealthy Tasks | < 1 healthy | Email alert |
| RDS CPU | > 80% (5 min) | Email alert |
| RDS Storage | < 10 GB free | Email alert |

### Logs

All logs are sent to CloudWatch Logs:
- Backend: `/ecs/prequal-backend`
- Frontend: `/ecs/prequal-frontend`

## Environment Variables

### Required Variables

Set these in AWS Systems Manager Parameter Store or Secrets Manager:

```bash
# Secret Key (64 character random string)
/aws/ssm/prequal/production/secret-key

# Database URL (auto-populated by Terraform)
# Format: postgresql://user:password@host:port/dbname
```

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment name | `production` |
| `DATABASE_URL` | PostgreSQL connection | From Secrets Manager |
| `REDIS_URL` | Redis connection | Auto-configured |
| `SECRET_KEY` | JWT signing key | From SSM |
| `LOG_LEVEL` | Logging level | `WARNING` |
| `ALLOWED_ORIGINS` | CORS origins | Production domain |

## Security

### Network Security

- ✅ VPC isolation
- ✅ Private subnets for services
- ✅ Security groups with minimal access
- ✅ No public database access

### Application Security

- ✅ Non-root Docker containers
- ✅ Secrets in AWS Secrets Manager
- ✅ Encrypted RDS storage
- ✅ TLS 1.2 for HTTPS

### Compliance

- ✅ HIPAA eligible architecture
- ✅ SOC 2 controls supported
- ✅ Encryption at rest and in transit

## Cost Estimation

### Monthly Costs (Approximate)

| Resource | Cost (USD) |
|----------|-----------|
| ECS Fargate (2 services) | ~$150 |
| RDS PostgreSQL (db.t3.medium) | ~$125 |
| ElastiCache Redis (cache.t3.medium) | ~$50 |
| ALB | ~$25 |
| Data Transfer | ~$20 |
| CloudWatch Logs | ~$10 |
| **Total** | **~$380/month** |

*Note: Costs vary based on traffic and region*

## Disaster Recovery

### Backup Strategy

- **RDS**: Automated daily backups, 30-day retention
- **Redis**: Persistence enabled (AOF)
- **Terraform State**: S3 with versioning

### Recovery Procedures

#### Database Restore

```bash
# List available snapshots
aws rds describe-db-snapshots --db-instance-identifier prequal-db

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier prequal-db-restored \
  --db-snapshot-identifier arn:aws:rds:...
```

#### Full Infrastructure Restore

```bash
# Apply Terraform (creates new resources)
terraform apply

# Deploy application
./scripts/deploy.sh deploy latest
```

## Troubleshooting

### Common Issues

#### ECS Tasks Won't Start

```bash
# Check task definition
aws ecs describe-task-definition --task-definition prequal-backend

# View container logs
aws logs tail /ecs/prequal-backend --follow
```

#### ALB Health Checks Failing

1. Verify backend is running on port 8000
2. Check health check endpoint: `/health`
3. Review security group rules

#### Database Connection Errors

1. Verify RDS is in same VPC
2. Check security group allows port 5432
3. Validate credentials in Secrets Manager

## CI/CD Integration

### GitHub Actions

The infrastructure integrates with GitHub Actions workflows:

- `.github/workflows/docker-build.yml` - Build and push images
- `.github/workflows/fastapi-backend.yml` - Backend tests and deploy
- `.github/workflows/ci-cd.yml` - Full CI/CD pipeline

### Deployment from CI/CD

```yaml
- name: Deploy to Production
  run: |
    ./scripts/deploy.sh deploy ${{ github.sha }} --endpoint https://prequal.yourcompany.com
```

## Maintenance

### Updating Infrastructure

```bash
# Update Terraform code
terraform plan -out=tfplan

# Apply changes
terraform apply tfplan
```

### Scaling Services

```bash
# Update desired count in Terraform
# Then apply
terraform apply

# Or use AWS CLI
aws ecs update-service \
  --cluster prequal-cluster \
  --service prequal-backend-service \
  --desired-count 4
```

## Outputs

After `terraform apply`, you'll get:

```
vpc_id = vpc-xxxxxxxxx
ecs_cluster_name = prequal-cluster
backend_ecr_repository_url = xxxxx.dkr.ecr.us-east-1.amazonaws.com/prequal-platform/backend
frontend_ecr_repository_url = xxxxx.dkr.ecr.us-east-1.amazonaws.com/prequal-platform/frontend
rds_endpoint = prequal-db.xxxxx.us-east-1.rds.amazonaws.com:5432
redis_endpoint = prequal-redis.xxxxx.cache.amazonaws.com:6379
database_secret_arn = arn:aws:secretsmanager:...
```

## Support

For issues or questions:
- Check monitoring dashboard
- Review CloudWatch logs
- Contact DevOps team

---

**Last Updated**: 2026-05-18
**Maintained By**: DevOps Engineer
**Related Issues**: MID-45
