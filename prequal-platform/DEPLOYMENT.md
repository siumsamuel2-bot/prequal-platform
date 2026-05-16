# Prequal Platform - Staging Environment Deployment Guide

## Overview

This guide covers deploying the Prequal Subcontractor Compliance Platform to a staging environment using Docker Compose.

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose)
- Git
- Port availability: 3000 (frontend), 8000 (backend), 5432 (PostgreSQL), 6379 (Redis)

## Quick Start

### 1. Clone and Navigate

```bash
cd prequal-platform
```

### 2. Configure Environment Variables

Copy the example environment file and configure secrets:

```bash
cp .env.staging.example .env
```

**Required changes before deployment:**

| Variable | Description | Action Required |
|----------|-------------|-----------------|
| `SECRET_KEY` | JWT signing key | Generate secure random value |
| `POSTGRES_PASSWORD` | Database password | Set strong password |
| `PGADMIN_PASSWORD` | PGAdmin password | Set strong password |

**Generate secure values:**

```bash
# Generate SECRET_KEY (Python)
python -c "import secrets; print(secrets.token_hex(32))"

# Or use OpenSSL
openssl rand -hex 32
```

### 3. Start the Stack

```bash
docker compose -f docker-compose.staging.yml --env-file .env up --build
```

### 4. Verify Deployment

Check service health:

| Service | URL | Expected Response |
|---------|-----|-------------------|
| Frontend | http://localhost:3000 | React app loads |
| Backend API | http://localhost:8000/health | `{"status":"healthy"}` |
| PostgreSQL | localhost:5432 | Connection successful |
| Redis | localhost:6379 | PONG response |
| PGAdmin | http://localhost:5050 | Login page |

**PGAdmin Credentials:**
- Email: `admin@prequal.local` (or from `.env`)
- Password: Value from `.env` (`PGADMIN_PASSWORD`)

**Database Connection in PGAdmin:**
- Host: `db`
- Port: `5432`
- Database: `prequal_staging`
- Username: `postgres`
- Password: Your `POSTGRES_PASSWORD` value

## Architecture

### Services

```
┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │
│  (React)    │     │  (FastAPI)  │
│  :3000      │     │    :8000    │
└─────────────┘     └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │PostgreSQL│ │  Redis   │ │ PGAdmin  │
        │  :5432   │ │  :6379   │ │  :5050   │
        └──────────┘ └──────────┘ └──────────┘
```

### Network Topology

All services communicate over the `prequal-network` bridge network:
- Frontend → Backend: `http://backend:8000`
- Backend → Database: `postgresql://db:5432`
- Backend → Redis: `redis://redis:6379`

### Volumes

Persistent data stored in Docker volumes:
- `postgres_data` - Database files
- `redis_data` - Redis persistence (AOF)
- `pgadmin_data` - PGAdmin configuration

## Configuration Reference

### Environment Variables

#### Backend (FastAPI)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `staging` | Environment name |
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `SECRET_KEY` | (required) | JWT signing key |
| `DEBUG` | `false` | Debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ALLOWED_ORIGINS` | (configurable) | CORS origins |
| `RATE_LIMIT_PER_MINUTE` | `60` | API rate limit |

#### Frontend (React)

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ENV` | `staging` | Node environment |
| `VITE_API_URL` | `/api` | Backend API URL |
| `VITE_APP_NAME` | `Prequal Platform` | App title |

### Docker Compose Profiles

The staging compose file includes:
- **backend**: FastAPI application (uvicorn)
- **frontend**: React SPA (nginx)
- **db**: PostgreSQL 15
- **redis**: Redis 7 with persistence
- **pgadmin**: Database management UI

## Common Operations

### Start Services

```bash
# Start all services
docker compose -f docker-compose.staging.yml --env-file .env up -d

# Start specific service
docker compose -f docker-compose.staging.yml --env-file .env up -d backend
```

### Stop Services

```bash
# Stop all services
docker compose -f docker-compose.staging.yml --env-file .env down

# Stop and remove volumes (⚠️ destructive)
docker compose -f docker-compose.staging.yml --env-file .env down -v
```

### View Logs

```bash
# All services
docker compose -f docker-compose.staging.yml --env-file .env logs -f

# Specific service
docker compose -f docker-compose.staging.yml --env-file .env logs -f backend
```

### Database Migrations

Migrations run automatically on backend startup via Alembic. To run manually:

```bash
docker compose -f docker-compose.staging.yml --env-file .env exec backend alembic upgrade head
```

### Access Backend Shell

```bash
docker compose -f docker-compose.staging.yml --env-file .env exec backend python
```

### Rebuild Services

```bash
# Rebuild backend
docker compose -f docker-compose.staging.yml --env-file .env build backend

# Rebuild frontend
docker compose -f docker-compose.staging.yml --env-file .env build frontend

# Rebuild all
docker compose -f docker-compose.staging.yml --env-file .env build
```

## Troubleshooting

### Backend won't start

Check database connectivity:
```bash
docker compose -f docker-compose.staging.yml --env-file .env logs db
docker compose -f docker-compose.staging.yml --env-file .env logs backend
```

Common issues:
- Database not ready: Wait for `db` health check to pass
- Missing env vars: Verify `.env` file exists and has required values
- Port conflict: Change host ports in compose file

### Frontend can't connect to backend

Verify API URL configuration:
1. Check `VITE_API_URL` in `.env`
2. Ensure backend is healthy: `curl http://localhost:8000/health`
3. Check CORS settings: `ALLOWED_ORIGINS` must include frontend URL

### Database connection issues

```bash
# Test database connection
docker compose -f docker-compose.staging.yml --env-file .env exec db pg_isready -U postgres -d prequal_staging

# View database logs
docker compose -f docker-compose.staging.yml --env-file .env logs db
```

### Reset database (⚠️ destructive)

```bash
# Remove volume
docker volume rm <project-name>_postgres_data

# Or use compose down -v
docker compose -f docker-compose.staging.yml --env-file .env down -v
```

## Security Notes

### Staging Environment

This configuration is for **staging only**. Before production:

1. **Secrets Management**: Replace `.env` file with Docker secrets or external secret manager
2. **Network Isolation**: Use separate networks, restrict inter-service communication
3. **Database Access**: Remove PGAdmin or restrict access with authentication
4. **SSL/TLS**: Configure HTTPS for frontend and encrypt database connections
5. **Image Scanning**: Scan Docker images for vulnerabilities
6. **Resource Limits**: Add CPU/memory limits to containers

### Required for Production

- [ ] Use production-grade database (managed RDS/Cloud SQL)
- [ ] Enable SSL/TLS for all services
- [ ] Configure proper secrets management (Vault, AWS Secrets Manager)
- [ ] Add monitoring and alerting (Prometheus, Grafana)
- [ ] Implement backup strategy for database
- [ ] Configure log aggregation
- [ ] Add resource limits to containers
- [ ] Remove or secure PGAdmin

## File References

| File | Purpose |
|------|---------|
| `docker-compose.staging.yml` | Main compose configuration |
| `Dockerfile.backend` | Backend container build |
| `Dockerfile.frontend` | Frontend container build |
| `.env.staging.example` | Environment template |
| `nginx.conf` | Nginx reverse proxy config |
| `database/init.sql` | Database initialization |

## Next Steps

1. **CI/CD Integration**: Set up automated deployments
2. **Monitoring**: Add health check dashboards
3. **Backup Strategy**: Configure automated database backups
4. **Load Testing**: Validate performance under load

---

**Last Updated**: 2026-05-11  
**Maintained By**: DevOps Engineer  
**Related Issues**: [MID-32](/MID/issues/MID-32)
