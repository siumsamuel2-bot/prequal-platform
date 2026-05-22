# Production Deployment Guide

## Overview

This guide covers the complete production deployment process for the Prequal Platform, including infrastructure setup, deployment procedures, and post-deployment verification.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Production Stack                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Traefik (Reverse Proxy)                                    │
│  ├─ Port 80 (HTTP → HTTPS redirect)                         │
│  └─ Port 443 (HTTPS with Let's Encrypt SSL)                │
│                                                              │
│  Frontend (React + Nginx)                                   │
│  ├─ Port 80                                                  │
│  └─ Static files + API proxy                               │
│                                                              │
│  Backend (FastAPI + Uvicorn)                                │
│  ├─ Port 8000                                                │
│  └─ REST API endpoints                                      │
│                                                              │
│  PostgreSQL 15 (Database)                                   │
│  ├─ Port 5432 (internal only)                               │
│  └─ Persistent volume                                       │
│                                                              │
│  Redis 7 (Cache & Sessions)                                 │
│  ├─ Port 6379 (internal only)                               │
│  └─ AOF persistence                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Infrastructure Requirements

- **Server**: Ubuntu 22.04+ with Docker 24+ and Docker Compose 2.20+
- **CPU**: Minimum 4 cores (8+ recommended)
- **RAM**: Minimum 8GB (16GB+ recommended)
- **Storage**: 50GB+ SSD with proper IOPS
- **Network**: Public IP with ports 80 and 443 open

### Required Tools

```bash
docker --version  # 24.0.0+
docker-compose --version  # 2.20.0+
```

### Environment Variables Template

Create a `.env` file in the production directory:

```bash
# Production Environment Variables
# Copy this to .env and fill in actual values

# Security
SECRET_KEY=<generate-with: openssl rand -hex 32>
POSTGRES_PASSWORD=<strong-random-password>

# Domain Configuration
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

# CORS
ALLOWED_ORIGINS=https://prequal.yourcompany.com

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# Email Configuration (optional)
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=noreply@yourcompany.com
SMTP_PASSWORD=<smtp-password>
EMAIL_FROM=noreply@yourcompany.com

# OSHA API (optional)
OSHA_API_KEY=<your-osha-api-key>

# Monitoring
ALERT_EMAIL=admin@yourcompany.com
```

## Deployment Steps

### Step 1: Server Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo systemctl enable docker
sudo systemctl start docker

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version

# Create application directory
sudo mkdir -p /opt/prequal-platform
cd /opt/prequal-platform

# Copy deployment files
# - docker-compose.production.yml
# - .env (with secrets)
# - traefik/ directory
```

### Step 2: Configure Traefik (Reverse Proxy with SSL)

Create `traefik/traefik.yml`:

```yaml
api:
  dashboard: true
  insecureEntrypoint: false

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https

  websecure:
    address: ":443"

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
  file:
    filename: /etc/traefik/dynamic.yml
    watch: true

certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@yourcompany.com
      storage: /etc/traefik/acme.json
      httpChallenge:
        entryPoint: web
```

Create `traefik/acme.json`:

```bash
touch traefik/acme.json
chmod 600 traefik/acme.json
```

### Step 3: Deploy Application Stack

```bash
# Pull latest images
docker compose -f docker-compose.production.yml pull

# Run database migrations
docker compose -f docker-compose.production.yml run --rm backend alembic upgrade head

# Start all services
docker compose -f docker-compose.production.yml up -d

# View logs
docker compose -f docker-compose.production.yml logs -f
```

### Step 4: Verify Deployment

```bash
# Check all services are running
docker compose -f docker-compose.production.yml ps

# Test health endpoints
curl -f https://prequal.yourcompany.com/health
curl -f https://prequal.yourcompany.com/health/live
curl -f https://prequal.yourcompany.com/health/ready

# Expected response:
# {"status":"healthy","timestamp":"2026-05-22T...","service":"prequal-api"}
```

### Step 5: Create Initial Admin User

```bash
# Run admin creation script
docker compose -f docker-compose.production.yml exec backend python -m api.create_admin
```

## Database Migrations

### Running Migrations

Migrations are automatically run on deployment. To run manually:

```bash
# Current version
docker compose -f docker-compose.production.yml exec backend alembic current

# Upgrade to latest
docker compose -f docker-compose.production.yml exec backend alembic upgrade head

# Downgrade one version
docker compose -f docker-compose.production.yml exec backend alembic downgrade -1

# View migration history
docker compose -f docker-compose.production.yml exec backend alembic history
```

### Creating New Migrations

```bash
# Generate new migration (in development)
alembic revision -m "description_of_change"

# Apply to development
alembic upgrade head

# Commit migration file to git
git add prequal-platform/alembic/versions/xxxx_description.py
```

## Monitoring & Logging

### View Logs

```bash
# All services
docker compose -f docker-compose.production.yml logs -f

# Specific service
docker compose -f docker-compose.production.yml logs -f backend
docker compose -f docker-compose.production.yml logs -f frontend

# Last 100 lines
docker compose -f docker-compose.production.yml logs --tail=100 backend
```

### Health Checks

| Endpoint | Description | Expected Response |
|----------|-------------|-------------------|
| `/health` | Basic health check | 200 OK |
| `/health/live` | Liveness probe | 200 OK |
| `/health/ready` | Readiness probe | 200 OK (all deps healthy) |
| `/health/detailed` | Detailed status | 200 OK with service status |

### Resource Monitoring

```bash
# Container resource usage
docker stats

# Disk usage
docker system df

# Remove unused data
docker system prune -a
```

## Backup & Recovery

### Database Backup

```bash
# Backup to file
docker compose -f docker-compose.production.yml exec db pg_dump -U postgres prequal_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Compress backup
gzip backup_*.sql

# Automated daily backups (cron)
0 2 * * * cd /opt/prequal-platform && docker compose -f docker-compose.production.yml exec db pg_dump -U postgres prequal_prod | gzip > /backups/db_$(date +\%Y\%m\%d_\%H\%M\%S).sql.gz
```

### Database Restore

```bash
# Restore from backup
gunzip backup_20260522_020000.sql.gz
docker compose -f docker-compose.production.yml exec -T db psql -U postgres -d prequal_prod < backup_20260522_020000.sql
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker compose -f docker-compose.production.yml logs backend

# Validate environment
docker compose -f docker-compose.production.yml config

# Restart services
docker compose -f docker-compose.production.yml restart backend
```

### Database Connection Issues

```bash
# Check database is running
docker compose -f docker-compose.production.yml ps db

# Test database connection
docker compose -f docker-compose.production.yml exec db psql -U postgres -d prequal_prod

# Check DATABASE_URL in .env
docker compose -f docker-compose.production.yml exec backend env | grep DATABASE
```

### SSL Certificate Issues

```bash
# Check Traefik logs
docker compose -f docker-compose.production.yml logs traefik

# Verify acme.json permissions
ls -la traefik/acme.json
# Should be: -rw------- (600)

# Force certificate renewal
docker compose -f docker-compose.production.yml exec traefik traefik version
```

## Security Checklist

- [ ] All secrets in `.env` file (not in git)
- [ ] `acme.json` has 600 permissions
- [ ] Database port 5432 not exposed to public
- [ ] Firewall configured (only 80, 443 open)
- [ ] Regular system updates scheduled
- [ ] Backup strategy implemented
- [ ] Monitoring alerts configured
- [ ] Rate limiting enabled (60 req/min)
- [ ] CORS configured for production domain only

## Rollback Procedure

If deployment fails:

```bash
# 1. Stop new deployment
docker compose -f docker-compose.production.yml down

# 2. Restore previous Docker image
# (tag was saved in deployment log)

# 3. Restore database if needed
# (from pre-deployment backup)

# 4. Restart previous version
docker compose -f docker-compose.production.yml up -d
```

## CI/CD Integration

### GitHub Actions Deployment

The production deployment is automated via GitHub Actions:

1. Push to `main` triggers build
2. Tag with `v*` triggers production deployment
3. Manual trigger available for emergency deployments

See `.github/workflows/production-deployment.yml` for details.

### Manual Deployment Override

```bash
# From CI/CD artifacts
docker pull ghcr.io/your-org/prequal-platform-backend:latest
docker pull ghcr.io/your-org/prequal-platform-frontend:latest

# Deploy with new images
docker compose -f docker-compose.production.yml up -d --no-deps backend frontend
```

## Support & Contacts

- **Infrastructure Issues**: Check monitoring dashboard
- **Application Errors**: Review backend logs
- **Database Issues**: Contact database administrator
- **Security Incidents**: Follow incident response procedure

---

**Last Updated**: 2026-05-22  
**Version**: 1.0.0  
**Maintained By**: DevOps Engineer
