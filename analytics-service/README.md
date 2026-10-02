# Prequal Analytics Service

Event ingestion, reporting, and anomaly detection microservice for the Prequal platform. Extracted from the monolith as Phase 1 of the microservice architecture (ADR-001 / MID-514), per MID-588.

## Responsibilities

- Analytics event ingestion (Redis Streams + direct-write fallback)
- Feature adoption and system health reporting
- Pilot customer engagement metrics
- Anomaly detection (zero usage, usage drops, error rate spikes)
- Dashboard configurations

## Stack

- Python 3.12 / FastAPI
- PostgreSQL (service-owned database, `analytics_service`)
- Redis Streams (event ingestion pipeline)
- Port: 8006

## Quick start (local)

```bash
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./dev.db
export SERVICE_API_KEY=dev-service-key
uvicorn app.main:app --host 0.0.0.0 --port 8006
```

With Docker Compose (from `prequal-platform/`):

```bash
docker compose up analytics analytics-worker analytics-db
```

## Ingestion worker

Drains the Redis stream (`analytics:events`) into the analytics database:

```bash
python -m app.worker
```

## Authentication

- **Service-to-service:** `X-Service-Api-Key` header (constant-time compare, fail-closed)
- **User context:** trusted `X-User-Id` / `X-User-Role` / `X-Organization-Id` headers set by the gateway/monolith after session validation; only honored with a valid service key
- Non-admin callers are org-scoped (org/team isolation per MID-544/545/546/547)

See [docs/API_CONTRACT.md](docs/API_CONTRACT.md) for the full API contract.

## Database

Service-owned PostgreSQL database with schema in `database/schema.sql` (auto-applied on container init in docker-compose). Tables: `analytics_events`, `feature_usage_events`, `system_health_metrics`, `dashboard_configs`, plus materialized views for daily aggregation.

## Tests

```bash
pytest tests/ -v
```

## CI/CD

`.github/workflows/analytics-service.yml` — lint, tests (Postgres service), Docker build/push to GHCR, Trivy scan, staging/production deploy stubs.
