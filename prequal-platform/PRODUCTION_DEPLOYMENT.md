# Prequal Platform - Production Deployment Runbook

## Overview

This runbook provides step-by-step instructions for deploying the Prequal Subcontractor Compliance Platform to a production environment using Docker Compose.

**Last Updated**: 2026-05-11  
**Maintained By**: DevOps Engineer  
**Related Issues**: [MID-34](/MID/issues/MID-34)

---

## Prerequisites

### Infrastructure Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| Memory | 8 GB | 16 GB |
| Disk | 50 GB SSD | 100 GB SSD |
| Network | 1 Gbps | 1 Gbps |

### Software Requirements

- Docker Engine 24.0+ or Docker Desktop
- Docker Compose 2.0+
- Git
- SSL/TLS certificates (for production HTTPS)
- Domain name configured for production server

### Security Requirements

- Firewall configured (ports 80, 443, 22 only)
- Fail2ban or similar intrusion prevention
- Regular security updates enabled
- Backup strategy in place

---

## Pre-Deployment Checklist

- [ ] All secrets generated and stored securely
- [ ] Domain DNS records configured
- [ ] SSL/TLS certificates obtained
- [ ] Database backup strategy tested
- [ ] Monitoring and alerting configured
- [ ] Load testing completed
- [ ] Security scan passed (no critical vulnerabilities)
- [ ] Rollback plan documented
- [ ] Team notified of deployment window

---

## Deployment Steps

### Step 1: Prepare Environment Variables

Create a production environment file with secure secrets:

```bash
cd prequal-platform
cp .env.staging.example .env.production
```

**Required environment variables:**

| Variable | Description | How to Generate |
|----------|-------------|-----------------|
| `SECRET_KEY` | JWT signing key (64 chars) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `POSTGRES_PASSWORD` | Database password | `openssl rand -base64 32` |
| `ALLOWED_ORIGINS` | Production domain | `https://prequal.yourcompany.com` |
| `SMTP_*` | Email configuration | From email provider |
| `OSHA_API_KEY` | OSHA integration | From OSHA API portal |

**Example `.env.production`:**

```bash
# Production Environment Configuration
# NEVER commit this file to version control

# Environment
ENVIRONMENT=production

# Security - Generate secure random values
SECRET_KEY=<64-character-hex-string>
ALLOWED_ORIGINS=https://prequal.yourcompany.com

# Database
POSTGRES_PASSWORD=<32-character-random-string>

# Email (SMTP)
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=noreply@yourcompany.com
SMTP_PASSWORD=<app-password>
EMAIL_FROM=noreply@yourcompany.com

# OSHA API
OSHA_API_KEY=<your-osha-api-key>
```

**Security Note**: Store `.env.production` with restricted permissions:

```bash
chmod 600 .env.production
chown root:root .env.production
```

### Step 2: Load Environment Variables

```bash
set -a
source .env.production
set +a
```

### Step 3: Validate Docker Images

Ensure production Docker images are built and available:

```bash
# Pull latest production images
docker compose -f docker-compose.prod.yml pull

# Or build from source
docker compose -f docker-compose.prod.yml build
```

### Step 4: Start Production Stack

```bash
# Start all services
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# Verify all services are running
docker compose -f docker-compose.prod.yml ps
```

Expected output:
```
NAME                    STATUS         HEALTH
prequal-backend-prod    Up (healthy)   
prequal-frontend-prod   Up (healthy)   
prequal-db-prod         Up (healthy)   
prequal-redis-prod      Up (healthy)   
```

### Step 5: Verify Health Checks

```bash
# Check backend health
curl -f http://localhost:8000/health

# Expected: {"status":"healthy","environment":"production"}

# Check frontend
curl -f http://localhost/

# Expected: HTML response with status 200

# Check database
docker compose -f docker-compose.prod.yml exec db pg_isready -U postgres -d prequal_prod

# Expected: accepting connections
```

### Step 6: Verify Logs

```bash
# Check for errors in backend logs
docker compose -f docker-compose.prod.yml logs backend | grep -i error

# Check frontend logs
docker compose -f docker-compose.prod.yml logs frontend

# Check database logs
docker compose -f docker-compose.prod.yml logs db
```

### Step 7: Run Database Migrations

Migrations run automatically on backend startup. To verify or run manually:

```bash
docker compose -f docker-compose.prod.yml exec backend alembic current
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### Step 8: Configure HTTPS (Optional but Recommended)

For production, configure reverse proxy with SSL/TLS:

**Option A: Using nginx-proxy with Let's Encrypt**

```bash
# Add to docker-compose.prod.yml or use separate proxy service
docker run -d \
  --name nginx-proxy \
  -p 80:80 \
  -p 443:443 \
  -v /var/run/docker.sock:/tmp/docker.sock:ro \
  -v /etc/nginx/certs:/etc/nginx/certs:ro \
  nginxproxy/nginx-proxy

docker run -d \
  --name letsencrypt-companion \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /etc/nginx/certs:/etc/nginx/certs:rw \
  nginxproxy/acme-companion
```

**Option B: Manual SSL Configuration**

Update `nginx.conf` with SSL certificates:

```nginx
server {
    listen 443 ssl http2;
    server_name prequal.yourcompany.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Step 9: Configure Firewall

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (for Let's Encrypt)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Verify
sudo ufw status
```

### Step 10: Final Verification

| Check | Command | Expected Result |
|-------|---------|-----------------|
| Frontend | `curl -I https://prequal.yourcompany.com` | HTTP 200 |
| Backend API | `curl -I https://prequal.yourcompany.com/api/health` | HTTP 200 |
| Database | `docker compose exec db pg_isready -U postgres` | accepting connections |
| Redis | `docker compose exec redis redis-cli ping` | PONG |
| Logs | `docker compose logs --tail=50` | No errors |

---

## Post-Deployment Tasks

### 1. Backup Database

```bash
# Create backup directory
mkdir -p ./database/backups

# Run backup
docker compose -f docker-compose.prod.yml exec db pg_dump -U postgres prequal_prod | gzip > ./database/backups/prequal_prod_$(date +%Y%m%d_%H%M%S).sql.gz

# Verify backup exists
ls -lh ./database/backups/
```

### 2. Set Up Monitoring

Refer to [MONITORING.md](./MONITORING.md) for detailed monitoring configuration.

Quick start:

```bash
# Start monitoring stack
docker compose -f docker-compose.monitoring.yml up -d

# Access Grafana
# URL: http://localhost:3001 (default credentials: admin/admin)
```

### 3. Test Rollback Procedure

```bash
# Tag current state
docker compose -f docker-compose.prod.yml ps > rollback-state.txt

# Rollback to previous image version
docker compose -f docker-compose.prod.yml pull backend:previous-tag
docker compose -f docker-compose.prod.yml up -d backend
```

---

## Common Operations

### Start Services

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

### Stop Services

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
```

### Restart Services

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production restart
```

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

### Scale Services

```bash
# Scale backend to 3 instances (requires load balancer)
docker compose -f docker-compose.prod.yml up -d --scale backend=3
```

### Update Images

```bash
# Pull latest images
docker compose -f docker-compose.prod.yml pull

# Zero-downtime deployment
docker compose -f docker-compose.prod.yml up -d --no-deps --build backend
docker compose -f docker-compose.prod.yml up -d --no-deps --build frontend
```

### Database Backup (Automated)

Add cron job for daily backups:

```bash
# crontab -e
0 2 * * * cd /path/to/prequal-platform && docker compose -f docker-compose.prod.yml exec db pg_dump -U postgres prequal_prod | gzip > ./database/backups/prequal_prod_$(date +\%Y\%m\%d_\%H\%M\%S).sql.gz
```

### Database Restore

```bash
# Stop application
docker compose -f docker-compose.prod.yml down

# Restore from backup
gunzip < ./database/backups/prequal_prod_20260511_020000.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U postgres -d prequal_prod

# Restart application
docker compose -f docker-compose.prod.yml up -d
```

---

## Troubleshooting

### Backend Won't Start

**Symptoms**: Container exits immediately, health check fails

**Check logs**:
```bash
docker compose -f docker-compose.prod.yml logs backend
```

**Common issues**:
- Database not ready: Wait for `db` health check
- Missing environment variables: Verify `.env.production`
- Port conflicts: Check `docker compose ps`

### Database Connection Errors

**Symptoms**: Backend logs show connection refused

**Solutions**:
```bash
# Check database is running
docker compose -f docker-compose.prod.yml ps db

# Test connection
docker compose -f docker-compose.prod.yml exec db pg_isready -U postgres -d prequal_prod

# Check DATABASE_URL format
echo $DATABASE_URL
```

### High Memory Usage

**Symptoms**: Container killed by OOM killer

**Solutions**:
1. Check resource limits in `docker-compose.prod.yml`
2. Scale horizontally instead of vertically
3. Add Redis caching
4. Optimize database queries

### Frontend Returns 502 Bad Gateway

**Symptoms**: Nginx error, backend unreachable

**Solutions**:
```bash
# Check backend health
curl http://localhost:8000/health

# Verify network connectivity
docker compose -f docker-compose.prod.yml exec frontend ping backend

# Check CORS settings
# ALLOWED_ORIGINS must include frontend domain
```

---

## Security Hardening

### Container Security

- [x] Non-root users in Dockerfiles
- [x] Minimal base images (alpine, slim)
- [x] No secrets in images
- [ ] Image scanning (Trivy integrated in CI/CD)
- [ ] Regular security updates

### Network Security

- [x] Isolated Docker network
- [ ] Firewall configured
- [ ] SSL/TLS enabled
- [ ] Rate limiting configured

### Application Security

- [x] Environment variables for secrets
- [x] CORS configured
- [x] Rate limiting enabled
- [ ] Regular dependency updates
- [ ] Security headers in nginx

---

## Performance Optimization

### Image Size Optimization

Current production images:
- Backend: ~150MB (multi-stage build)
- Frontend: ~25MB (nginx with static assets)

### Resource Limits

Configured in `docker-compose.prod.yml`:
- Backend: 2 CPU, 2GB RAM
- Frontend: 1 CPU, 512MB RAM
- Database: 2 CPU, 4GB RAM
- Redis: 0.5 CPU, 512MB RAM

### Caching Strategy

- Docker layer caching in CI/CD
- Redis for session/cache (configured)
- Browser caching via nginx (see `nginx.conf`)

---

## Disaster Recovery

### Backup Strategy

| Component | Frequency | Method | Retention |
|-----------|-----------|--------|-----------|
| Database | Daily | pg_dump + gzip | 30 days |
| Uploads | Daily | Volume backup | 30 days |
| Config | On change | Git repository | Indefinite |

### Recovery Time Objective (RTO)

- **Critical services**: 1 hour
- **Full recovery**: 4 hours

### Recovery Steps

1. Restore database from latest backup
2. Restore volume data (uploads)
3. Deploy application with known-good images
4. Verify health checks
5. Restore DNS if needed

---

## Environment Comparison

| Feature | Staging | Production |
|---------|---------|------------|
| Compose File | `docker-compose.staging.yml` | `docker-compose.prod.yml` |
| Debug Mode | Enabled | Disabled |
| PGAdmin | Included | Excluded |
| Resource Limits | None | Configured |
| Logging | Verbose (DEBUG) | Minimal (WARNING) |
| Backups | Manual | Automated |
| Monitoring | Basic | Full stack |
| SSL | Optional | Required |

---

## Support

**DevOps Team Contact**: [Add contact information]

**Escalation Path**:
1. Check this runbook
2. Review logs (`docker compose logs`)
3. Check monitoring (Grafana)
4. Contact DevOps Engineer
5. Escalate to CTO if critical

---

## Appendix A: Docker Compose Override Example

For production customizations, create `docker-compose.prod.override.yml`:

```yaml
version: '3.8'
services:
  backend:
    environment:
      - CUSTOM_VAR=value
  db:
    volumes:
      - /backup:/backup
```

Use with:
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.override.yml up -d
```

---

## Appendix B: Health Check Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Backend | `/health` | `{"status":"healthy"}` |
| Backend | `/health/live` | `{"alive":true}` |
| Backend | `/health/ready` | `{"ready":true}` |
| Frontend | `/` | HTTP 200 |
| Database | `pg_isready` | accepting connections |
| Redis | `redis-cli ping` | PONG |

---

**Document Version**: 1.0  
**Review Cycle**: Quarterly  
**Next Review**: 2026-08-11
