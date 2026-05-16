# Prequal Platform - Production Architecture

## Overview

This document describes the production deployment architecture for the Prequal Subcontractor Compliance Platform.

**Last Updated**: 2026-05-11  
**Maintained By**: DevOps Engineer  
**Related Issues**: [MID-34](/MID/issues/MID-34)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Production Environment                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Internet Layer                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │  │
│  │  │   Users     │  │  Subcontractors │  │  Admins     │      │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │  │
│  │         │                 │                 │             │  │
│  │         └─────────────────┼─────────────────┘             │  │
│  │                           │                               │  │
│  └───────────────────────────┼───────────────────────────────┘  │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                    Load Balancer (443)                     │  │
│  │                    SSL/TLS Termination                     │  │
│  └───────────────────────────┼───────────────────────────────┘  │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                   Application Layer                        │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │              Frontend (nginx)                       │  │  │
│  │  │  - React SPA (static assets)                       │  │  │
│  │  │  - Reverse proxy to backend                        │  │  │
│  │  │  - Port 80/443                                     │  │  │
│  │  │  - Resource limits: 1 CPU, 512MB RAM               │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                              │                              │  │
│  │  ┌───────────────────────────▼────────────────────────┐  │  │
│  │  │              Backend (FastAPI/Uvicorn)              │  │  │
│  │  │  - REST API endpoints                              │  │  │
│  │  │  - JWT authentication                              │  │  │
│  │  │  - Business logic                                  │  │  │
│  │  │  - Port 8000                                       │  │  │
│  │  │  - Resource limits: 2 CPU, 2GB RAM                 │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────┬───────────────────────────────┐  │
│  │                         │                                   │  │
│  │  ┌───────────────────────▼──┐  ┌────────────────────────┐ │  │
│  │  │   PostgreSQL (db)        │  │   Redis                │ │  │
│  │  │   - Persistent data      │  │   - Cache              │ │  │
│  │  │   - User data            │  │   - Sessions           │ │  │
│  │  │   - Compliance records   │  │   - Rate limiting      │ │  │
│  │  │   - Port 5432            │  │   - Port 6379          │ │  │
│  │  │   - 2 CPU, 4GB RAM       │  │   - 0.5 CPU, 512MB RAM │ │  │
│  │  └──────────────────────────┘  └────────────────────────┘ │  │
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│         prequal-network (bridge)                                   │
│         172.28.0.0/16                                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Frontend Service

| Property | Value |
|----------|-------|
| **Image** | `ghcr.io/{org}/prequal-platform-frontend:latest` |
| **Base** | nginx:alpine |
| **Port** | 80, 443 |
| **CPU Limit** | 1.0 |
| **Memory Limit** | 512MB |
| **Health Check** | `wget -q --spider http://localhost/` |
| **Restart Policy** | always |

**Purpose**: Serves the React single-page application (SPA) and reverse proxies API requests to the backend.

**Key Features**:
- Multi-stage build for minimal image size (~25MB)
- Non-root user (nginx)
- Gzip compression enabled
- Static asset caching

### Backend Service

| Property | Value |
|----------|-------|
| **Image** | `ghcr.io/{org}/prequal-platform-backend:latest` |
| **Base** | python:3.11-slim |
| **Port** | 8000 |
| **CPU Limit** | 2.0 |
| **Memory Limit** | 2GB |
| **Health Check** | `curl -f http://localhost:8000/health` |
| **Restart Policy** | always |

**Purpose**: FastAPI application providing REST API endpoints, authentication, and business logic.

**Key Features**:
- Multi-stage build with virtual environment
- Non-root user (appuser)
- Alembic migrations on startup
- Structured JSON logging
- Rate limiting

### Database Service

| Property | Value |
|----------|-------|
| **Image** | postgres:15-alpine |
| **Port** | 5432 (internal only) |
| **CPU Limit** | 2.0 |
| **Memory Limit** | 4GB |
| **Health Check** | `pg_isready -U postgres -d prequal_prod` |
| **Restart Policy** | always |

**Purpose**: PostgreSQL relational database for persistent data storage.

**Key Features**:
- Docker volume for persistence
- Automated backups via cron
- init.sql for schema initialization

### Redis Service

| Property | Value |
|----------|-------|
| **Image** | redis:7-alpine |
| **Port** | 6379 (internal only) |
| **CPU Limit** | 0.5 |
| **Memory Limit** | 512MB (with maxmemory policy) |
| **Health Check** | `redis-cli ping` |
| **Restart Policy** | always |

**Purpose**: In-memory data store for caching, sessions, and rate limiting.

**Key Features**:
- Append-only file (AOF) persistence
- LRU eviction policy
- Max memory: 256MB

---

## Network Architecture

### Network Topology

All services communicate over an isolated Docker bridge network:

```yaml
networks:
  prequal-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

### Service Communication

| Source | Destination | Protocol | Port | Purpose |
|--------|-------------|----------|------|---------|
| Frontend | Backend | HTTP | 8000 | API requests |
| Backend | Database | TCP | 5432 | Data persistence |
| Backend | Redis | TCP | 6379 | Caching/sessions |
| External | Frontend | HTTPS | 443 | User traffic |

### Firewall Rules

| Port | Protocol | Source | Destination | Purpose |
|------|----------|--------|-------------|---------|
| 443 | TCP | Internet | Frontend | HTTPS traffic |
| 80 | TCP | Internet | Frontend | HTTP redirect |
| 22 | TCP | Admin IPs | Host | SSH management |

---

## Data Flow

### User Request Flow

1. User accesses `https://prequal.yourcompany.com`
2. Load balancer terminates SSL/TLS
3. Request forwarded to Frontend (nginx)
4. Frontend serves static React app
5. React app makes API calls to `/api/*`
6. Frontend reverse proxies to Backend
7. Backend processes request, queries database/Redis
8. Response flows back through the chain

### Authentication Flow

1. User submits credentials to `/api/auth/login`
2. Backend validates against database
3. JWT token generated and returned
4. Frontend stores token (localStorage)
5. Subsequent requests include token in Authorization header
6. Backend validates token on each request

---

## Security Architecture

### Container Security

- **Non-root users**: All containers run as non-root users
- **Minimal base images**: Alpine/slim images reduce attack surface
- **No secrets in images**: All secrets via environment variables
- **Image scanning**: Trivy scans in CI/CD pipeline

### Network Security

- **Isolated network**: Services on private Docker network
- **No direct external access**: Only frontend exposed
- **SSL/TLS**: Encrypted communication (production)
- **Rate limiting**: API rate limiting configured

### Application Security

- **CORS**: Restricted to production domain
- **JWT**: Secure token-based authentication
- **SQL injection prevention**: ORM (SQLAlchemy) with parameterized queries
- **XSS prevention**: React's built-in escaping

---

## Scalability

### Horizontal Scaling

Frontend and backend can be scaled horizontally:

```bash
docker compose up -d --scale backend=3 --scale frontend=2
```

**Requirements for horizontal scaling**:
- Load balancer (nginx, Traefik, HAProxy)
- Shared session storage (Redis)
- Database connection pooling

### Vertical Scaling

Adjust resource limits in `docker-compose.prod.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 8G
```

---

## Monitoring & Logging

### Health Checks

All services implement health checks:

| Service | Endpoint/Command | Interval | Timeout |
|---------|------------------|----------|---------|
| Frontend | `wget -q --spider http://localhost/` | 30s | 5s |
| Backend | `curl -f http://localhost:8000/health` | 30s | 10s |
| Database | `pg_isready -U postgres -d prequal_prod` | 10s | 5s |
| Redis | `redis-cli ping` | 10s | 5s |

### Logging

- **Format**: JSON structured logging
- **Aggregation**: Docker json-file driver with rotation
- **Size limit**: 10MB per file, 3 files max
- **Access**: `docker compose logs -f <service>`

### Metrics

- Container resource usage (CPU, memory)
- Database connections
- Redis memory usage
- API response times
- Error rates

---

## Disaster Recovery

### Backup Strategy

| Component | Method | Frequency | Retention |
|-----------|--------|-----------|-----------|
| Database | pg_dump | Daily | 30 days |
| Uploads | Volume backup | Daily | 30 days |
| Configuration | Git repository | On change | Indefinite |

### Recovery Procedures

1. **Database restore**: `pg_restore` from latest backup
2. **Application restore**: Redeploy from known-good images
3. **Data restore**: Restore Docker volumes from backup

### RTO/RPO

- **RTO (Recovery Time Objective)**: 1 hour
- **RPO (Recovery Point Objective)**: 24 hours

---

## Deployment Workflow

### CI/CD Pipeline

```
┌─────────────┐     ┌──────────┐     ┌──────────┐     ┌─────────┐
│ Git Push    │────▶│ Build    │────▶│ Test     │────▶│ Scan    │
│ (main)      │     │ Images   │     │ Suite    │     │ (Trivy) │
└─────────────┘     └──────────┘     └──────────┘     └─────────┘
                                                       │
                                                       ▼
┌─────────────┐     ┌──────────┐     ┌──────────┐     ┌─────────┐
│ Production  │◀────│ Deploy   │◀────│ Push     │◀────│ Approve │
│ Deploy      │     │ (manual) │     │ to ECR   │     │         │
└─────────────┘     └──────────┘     └──────────┘     └─────────┘
```

### Deployment Steps

1. Merge PR to `main` branch
2. GitHub Actions builds Docker images
3. Images scanned for vulnerabilities
4. Images pushed to GitHub Container Registry
5. Manual approval for production deployment
6. Deploy to production server
7. Verify health checks
8. Monitor for issues

---

## Environment Comparison

| Feature | Staging | Production |
|---------|---------|------------|
| **Compose File** | `docker-compose.staging.yml` | `docker-compose.prod.yml` |
| **Debug Mode** | Enabled | Disabled |
| **Log Level** | INFO | WARNING |
| **Resource Limits** | None | Configured |
| **PGAdmin** | Included | Excluded |
| **SSL/TLS** | Optional | Required |
| **Backups** | Manual | Automated |
| **Monitoring** | Basic | Full stack |
| **Scaling** | Single instance | Scalable |

---

## Costs (Estimated)

### Infrastructure Costs (Monthly)

| Resource | Specification | Cost |
|----------|---------------|------|
| Compute (VM) | 4 vCPU, 8GB RAM | ~$80 |
| Storage | 100GB SSD | ~$20 |
| Data Transfer | 1TB/month | ~$10 |
| **Total** | | **~$110/month** |

### Optimization Opportunities

- Use spot instances for non-critical workloads
- Implement auto-scaling to reduce off-peak costs
- Optimize database queries to reduce resource usage

---

## Future Improvements

- [ ] Kubernetes orchestration for auto-scaling
- [ ] Multi-region deployment for HA
- [ ] Blue-green deployment strategy
- [ ] Automated canary deployments
- [ ] Service mesh (Istio) for advanced traffic management
- [ ] Centralized logging (ELK stack)
- [ ] Distributed tracing (Jaeger)

---

**Document Version**: 1.0  
**Review Cycle**: Quarterly  
**Next Review**: 2026-08-11
