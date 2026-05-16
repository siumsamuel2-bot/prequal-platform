# Prequal Platform Production Deployment Runbook

## Overview

This runbook documents the complete process for deploying the Prequal compliance platform to production.

## Prerequisites

### Infrastructure Requirements
- Server with Docker and Docker Compose installed (Ubuntu 22.04+ recommended)
- Minimum 4 vCPU, 8GB RAM (8 vCPU, 16GB RAM recommended)
- Public IP address with DNS configured
- Domain name: `prequal.yourcompany.com`
- Ports 80 (HTTP) and 443 (HTTPS) open

### Required Secrets
Before deployment, ensure you have:
1. **Domain name** - Production domain (e.g., `prequal.yourcompany.com`)
2. **Email address** - For Let's Encrypt SSL certificates
3. **SMTP credentials** - For email notifications
4. **OSHA API key** - If using OSHA integration
5. **PostgreSQL password** - Auto-generated secure random string

## Pre-Deployment Checklist

- [ ] Domain DNS records configured (A record pointing to server IP)
- [ ] Server firewall configured (allow ports 22, 80, 443)
- [ ] Docker and Docker Compose installed on server
- [ ] All secrets generated and stored securely
- [ ] `.env.production` file created from `.env.production.example`
- [ ] Backup strategy in place (database backups, file backups)
- [ ] Monitoring configured (optional but recommended)
- [ ] CI/CD pipeline tested in staging

## Deployment Steps

### Step 1: Server Setup

```bash
# SSH into production server
ssh user@production-server

# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker (if not already installed)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose (if not included)
sudo apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

### Step 2: Clone and Configure

```bash
# Clone repository
git clone https://github.com/yourcompany/prequal-platform.git
cd prequal-platform

# Copy environment file
cp .env.production.example .env.production

# Edit environment file with production values
nano .env.production

# Secure environment file
chmod 600 .env.production
```

### Step 3: Configure SSL Certificate

```bash
# Create Traefik ACME storage directory
mkdir -p traefik
touch traefik/acme.json
chmod 600 traefik/acme.json

# Update traefik.yml with your email
# Edit: email: admin@yourcompany.com
nano traefik/traefik.yml
```

### Step 4: Deploy Application

```bash
# Start all services
docker compose -f docker-compose.production.yml up -d

# View logs
docker compose -f docker-compose.production.yml logs -f

# Check service health
docker compose -f docker-compose.production.yml ps
```

### Step 5: Verify Deployment

```bash
# Check backend health
curl -f http://localhost:8000/health

# Check frontend
curl -f http://localhost:80

# Check SSL certificate (after first deployment)
curl -I https://prequal.yourcompany.com
```

## Post-Deployment Verification

- [ ] SSL certificate issued successfully (check Traefik dashboard)
- [ ] Backend health endpoint returns 200 OK
- [ ] Frontend loads without errors
- [ ] Database connection successful
- [ ] Email sending works (test notification)
- [ ] All containers running and healthy
- [ ] Logs show no critical errors

## Monitoring

### Check Service Status
```bash
docker compose -f docker-compose.production.yml ps
```

### View Logs
```bash
# All services
docker compose -f docker-compose.production.yml logs -f

# Specific service
docker compose -f docker-compose.production.yml logs -f backend
docker compose -f docker-compose.production.yml logs -f frontend
docker compose -f docker-compose.production.yml logs -f traefik
```

### Health Checks
- Backend: `https://prequal.yourcompany.com/health`
- Traefik Dashboard: `http://production-server:8080` (if enabled)

## Maintenance

### Update Application
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.production.yml up -d --build
```

### Database Backup
```bash
# Create backup
docker exec prequal-db-prod pg_dump -U postgres prequal_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
docker exec -i prequal-db-prod psql -U postgres prequal_prod < backup_FILE.sql
```

### Scale Services
```bash
# Scale backend instances
docker compose -f docker-compose.production.yml up -d --scale backend=2
```

## Rollback Procedure

If deployment fails:

```bash
# Stop new deployment
docker compose -f docker-compose.production.yml down

# Revert code
git checkout <previous-commit>

# Redeploy
docker compose -f docker-compose.production.yml up -d
```

## Troubleshooting

### SSL Certificate Not Issuing
- Check domain DNS points to correct IP
- Verify port 80 is accessible from internet
- Check Traefik logs: `docker compose logs traefik`

### Database Connection Failed
- Verify POSTGRES_PASSWORD matches in .env.production
- Check db container is healthy: `docker compose ps`
- Review database logs: `docker compose logs db`

### Backend Not Starting
- Check all environment variables in .env.production
- Verify database migrations: `docker compose logs backend`
- Check dependencies are running: `docker compose ps`

## Security Notes

- Never commit `.env.production` to version control
- Rotate secrets quarterly
- Keep Docker and system packages updated
- Monitor logs for suspicious activity
- Use strong passwords for all secrets
- Restrict server access via SSH keys only

## Support Contacts

- **DevOps Lead**: [Contact Info]
- **CTO**: [Contact Info]
- **Emergency**: [Phone Number]

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-15 | Initial deployment runbook |
