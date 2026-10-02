# Analytics Service — Deployment & Operations

**Issue:** MID-591
**Service:** `analytics-service` (Phase 1 microservice extraction per MID-514/MID-588)
**Date:** 2026-10-02
**Owner:** DevOps Engineer

---

## Architecture

| Component | Detail |
| --- | --- |
| Runtime | FastAPI (uvicorn), Python 3.12-slim, port **8006** |
| Containers | `analytics-service` (API) + `analytics-worker` (Redis stream consumer, `python -m app.worker`) |
| Compute | AWS ECS Fargate, cluster `prequal-cluster`, 2 desired tasks, 256 CPU / 512 MB |
| Database | Dedicated RDS PostgreSQL `prequal-analytics-db` (db.t3.micro, KMS-encrypted, 7-day backups) |
| Queue | Existing `prequal` ElastiCache Redis — stream `analytics:events`, consumer group `analytics-ingestors` |
| Routing | ALB path rule: `/analytics/*` and `/api/v1/analytics*` → `analytics-tg` (port 8006) |
| Registry | ECR `analytics-service` |

The service is deployed **independently of the monolith**: its own task definition, ECS service, target group, listener rule, database, and IAM role.

## CI/CD (`.github/workflows/analytics-service.yml`)

- **Triggers:** push/PR to `main`/`develop`/`master` with paths `analytics-service/**`; tags `v*`; manual dispatch (staging/production)
- **test:** pytest with coverage (self-contained SQLite conftest — no postgres service needed); coverage artifact uploaded
- **build:** Buildx with GHA layer cache (`cache-from: type=gha`, `cache-to: type=gha,mode=max`) → ECR; Trivy scan (CRITICAL/HIGH) blocks via SARIF upload
- **deploy-staging:** on `develop` push or manual dispatch — ECS rolling update, waits for stability, health check `/analytics/health`
- **deploy-production:** on `main`/`v*` tags — CodeDeploy blue-green via `analytics-service/appspec.yaml` (container port 8006)
- **rollback:** manual dispatch — redeploys the previous task definition revision, verifies health

## Infrastructure (terraform/analytics-service.tf)

- `aws_db_instance.analytics_db` + subnet group (private subnets, KMS via `rds_encryption`)
- `aws_ssm_parameter.analytics_database_url` (`/prequal/analytics/database-url`, SecureString)
- `aws_secretsmanager_secret.analytics_service_auth` (`SERVICE_API_KEY`, KMS-encrypted) — service-to-service auth; placeholders have `ignore_changes`, real values set out-of-band
- Analytics-scoped IAM role + policies (ECR pull, secrets/SSM/KMS decrypt)
- ECS task definition (API + worker containers), ECS service with `deployment_circuit_breaker { enable, rollback }` and 200%/100% rolling config
- CloudWatch log group `/ecs/analytics-service` (30-day retention)

## Monitoring & Observability

- **Prometheus:** `/metrics` ASGI endpoint ships in the service (`app/metrics.py`) — HTTP request metrics, `analytics_events_ingested_total`, `analytics_redis_stream_backlog`
- **CloudWatch alarms:** `analytics-service-high-error-rate`, `analytics-service-high-latency`, `analytics-service-unhealthy-hosts` — wired to the existing `prequal_alerts` SNS topic
- **Log aggregation:** awslogs driver → `/ecs/analytics-service` (API stream prefix `ecs`, worker prefix `worker`); the monolith's Grafana/Prometheus stack (`docker-compose.monitoring.yml`) scrapes service metrics

## Secrets / Env the service expects

`DATABASE_URL` (SSM), `SERVICE_API_KEY` (Secrets Manager), `REDIS_URL`, `ANALYTICS_EVENTS_STREAM`, `ANALYTICS_CONSUMER_GROUP`, `ENVIRONMENT`, optional `ORG_SERVICE_URL`, `CORS_ALLOWED_ORIGINS` (see `app/config.py`).

## Operational notes

1. **Before first deploy:** fill `SERVICE_API_KEY` into `prequal/analytics/service-auth` in Secrets Manager; set `analytics_db_password` in tfvars; run `terraform apply`.
2. **Worker scaling:** increase `desired_count` to scale both API + worker replicas; the consumer group deduplicates stream consumption.
3. **Rollback:** `workflow_dispatch` the `rollback` job with the target environment.
4. **Service auth:** downstream callers authenticate with `SERVICE_API_KEY` (see `app/services/service_auth.py` and `docs/API_CONTRACT.md`).
