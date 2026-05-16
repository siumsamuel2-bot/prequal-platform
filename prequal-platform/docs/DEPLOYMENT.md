# Prequal Platform - Staging Deployment Guide

## Overview

This guide covers the Docker Compose-based staging environment deployment for the Prequal compliance platform.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Frontend   │────▶│   Backend    │────▶│  Database   │
│  (nginx)    │     │  (FastAPI)   │     │ (PostgreSQL)│
│  Port 3000  │     │  Port 8000   │     │  Port 5432  │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Redis    │
                    │  Port 6379  │
                    └─────────────┘
```

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine + Docker Compose (Linux)
- Git
- At least 4GB of available RAM
- 10GB of available disk space

## Quick Start

### 1. Clone and Setup

```bash
cd prequal-platform

# Copy environment template
cp .env.staging.example .env

# Generate secure secret key (Linux/Mac)
openssl rand -hex 32

# Or use PowerShell (Windows)
# [System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator::GetBytes(32))
```

### 2. Configure Environment

Edit `.env` file with your settings:

```bash
# Required - Change these!
SECRET_KEY=<generated-secret-key>
POSTGRES_PASSWORD=<strong-database-password>
PGADMIN_PASSWORD=<pgadmin-password>
```

### 3. Start the Stack

```bash
# Build and start all services
docker-compose -f docker-compose.staging.yml up --build

# Or run in detached mode (recommended)
docker-compose -f docker-compose.staging.yml up -d --build
```

### 4. Verify Deployment

```bash
# Check service health
docker-compose -f docker-compose.staging.yml ps

# View logs
docker-compose -f docker-compose.staging.yml logs -f

# Test backend health endpoint
curl http://localhost:8000/health

# Test frontend
curl http://localhost:3000
```

## Services

| Service     | Port  | Description                    |
|-------------|-------|--------------------------------|
| frontend    | 3000  | React frontend (nginx)         |
| backend     | 8000  | FastAPI backend                |
| db          | 5432  | PostgreSQL database            |
| redis       | 6379  | Redis cache                    |
| pgadmin     | 5050  | Database management UI         |

## Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PGAdmin**: http://localhost:5050

## Common Operations

### Stop Services

```bash
docker-compose -f docker-compose.staging.yml down
```

### Stop and Remove Volumes

```bash
# WARNING: This deletes all data!
docker-compose -f docker-compose.staging.yml down -v
```

### View Logs

```bash
# All services
docker-compose -f docker-compose.staging.yml logs -f

# Specific service
docker-compose -f docker-compose.staging.yml logs -f backend
```

### Restart Services

```bash
# All services
docker-compose -f docker-compose.staging.yml restart

# Specific service
docker-compose -f docker-compose.staging.yml restart backend
```

### Database Operations

```bash
# Connect to database
docker-compose -f docker-compose.staging.yml exec db psql -U postgres -d prequal_staging

# Backup database
docker-compose -f docker-compose.staging.yml exec db pg_dump -U postgres prequal_staging > backup.sql

# Restore database
docker-compose -f docker-compose.staging.yml exec -T db psql -U postgres -d prequal_staging < backup.sql
```

### Redis Operations

```bash
# Connect to Redis CLI
docker-compose -f docker-compose.staging.yml exec redis redis-cli

# Check Redis memory usage
docker-compose -f docker-compose.staging.yml exec redis redis-cli INFO memory
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | `a1b2c3...` |
| `POSTGRES_PASSWORD` | Database password | `strong-password` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `PGADMIN_EMAIL` | PGAdmin login email | `admin@prequal.local` |
| `PGADMIN_PASSWORD` | PGAdmin password | `admin` |
| `OSHA_API_KEY` | OSHA API key for safety data | - |
| `SMTP_HOST` | Email server host | - |
| `SMTP_PORT` | Email server port | `587` |
| `SMTP_USER` | Email username | - |
| `SMTP_PASSWORD` | Email password | - |
| `EMAIL_FROM` | Sender email address | `noreply@prequal.local` |

## Troubleshooting

### Backend Won't Start

```bash
# Check logs
docker-compose -f docker-compose.staging.yml logs backend

# Common issues:
# 1. Database not ready - wait for db health check
# 2. Port already in use - change port in docker-compose.staging.yml
# 3. Missing env vars - check .env file
```

### Database Connection Failed

```bash
# Verify database is healthy
docker-compose -f docker-compose.staging.yml ps db

# Check database logs
docker-compose -f docker-compose.staging.yml logs db

# Test connection
docker-compose -f docker-compose.staging.yml exec db pg_isready -U postgres
```

### Frontend Returns 502

```bash
# Backend might not be ready
docker-compose -f docker-compose.staging.yml logs backend

# Restart frontend
docker-compose -f docker-compose.staging.yml restart frontend
```

### Clear All Data

```bash
# Stop and remove everything including volumes
docker-compose -f docker-compose.staging.yml down -v

# Remove images too (optional)
docker-compose -f docker-compose.staging.yml down -v --rmi all
```

## Health Checks

All services have health checks configured:

- **Backend**: HTTP GET /health (port 8000)
- **Frontend**: HTTP GET / (port 80)
- **Database**: pg_isready
- **Redis**: redis-cli ping

## Security Notes

### For Staging

- Use strong passwords
- Don't expose ports to public internet
- Keep `.env` file secure
- Regular dependency updates

### Before Production

- [ ] Change all default passwords
- [ ] Use production-grade secrets management
- [ ] Enable SSL/TLS
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerting
- [ ] Enable database backups
- [ ] Review and restrict CORS origins
- [ ] Remove PGAdmin or restrict access

## File Structure

```
prequal-platform/
├── docker-compose.staging.yml    # Staging environment config
├── Dockerfile.backend            # Backend container build
├── Dockerfile.frontend           # Frontend container build
├── nginx.conf                    # Nginx configuration
├── .env.staging.example          # Environment template
├── database/
│   └── init.sql                  # Database initialization
└── docs/
    └── DEPLOYMENT.md             # This file
```

## Next Steps

1. **CI/CD Integration**: Add automated testing and deployment
2. **Monitoring**: Set up Prometheus/Grafana for metrics
3. **Logging**: Configure centralized logging (ELK/Loki)
4. **Backups**: Implement automated database backups
5. **Production**: Create production docker-compose with SSL

## Support

For issues or questions, check:
- API Documentation: http://localhost:8000/docs
- Project documentation: ../docs/
- Issue tracker: [Company issue tracker]
