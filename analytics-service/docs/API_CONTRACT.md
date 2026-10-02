# Analytics Service — API Contract

**Service:** prequal-analytics-service
**Port:** 8006 (per ADR-001 / MID-514)
**Base path:** `/api/v1`
**Source issue:** MID-588

---

## Overview

The analytics service owns event ingestion, reporting queries, and anomaly detection for the Prequal platform. It was extracted from the monolith (Phase 1 of the MID-514 microservice roadmap, Strangler Fig pattern).

**Data ownership (database-per-service, shared-nothing):**
- `analytics_events` — analytics events (schema compatible with the monolith)
- `feature_usage_events` — feature adoption raw events (MID-88 schema)
- `system_health_metrics` — system health raw metrics (MID-88 schema)
- `dashboard_configs` — dashboard configurations
- `mv_feature_adoption_summary`, `mv_system_health_summary` — aggregated metrics (materialized views)

**Event ingestion pipeline:**
- Redis Streams (`analytics:events`) with consumer group `analytics-ingestors`
- Standalone worker (`python -m app.worker`) drains the stream; `POST /api/v1/analytics/ingestion/consume` can drain it on demand
- Direct-write fallback when Redis is unavailable (ingestion never blocks callers)

---

## Authentication

### Service-to-service (internal callers: gateway, monolith, services)

Requests carry a shared service API key:

```
X-Service-Api-Key: <SERVICE_API_KEY>
```

- Validated with constant-time comparison; **fail-closed** — if the key is unconfigured, service-authenticated requests are rejected
- Required on: `/ingestion/consume`, `/track-health`

### User context propagation

The gateway/monolith validates user sessions and forwards trusted headers:

```
X-User-Id: <user id>
X-User-Role: <role>
X-Organization-Id: <organization id>
```

- Trusted headers are only honored when the request also carries a valid `X-Service-Api-Key`
- Non-admin callers are pinned to their own organization (org/team isolation per MID-544/545/546/547)
- Required on: user-facing endpoints (`/events`, `/track-feature`, `/feature-adoption`, etc.)
- Admin-role endpoints: `/feature-adoption`, `/daily-active-users`, `/system-health`, `/weekly-report`, `/anomalies`, `/pilot-engagement`

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | none | Health check |
| POST | `/api/v1/analytics/events` | user context | Create an analytics event (201) |
| GET | `/api/v1/analytics/events` | user context | List events (org-scoped for non-admins; `organization_id`, `event_type`, `days`, `skip`, `limit`) |
| GET | `/api/v1/analytics/dashboard-configs` | user context | List dashboard configurations |
| POST | `/api/v1/analytics/dashboard-configs` | user context | Create a dashboard configuration (201) |
| POST | `/api/v1/analytics/track-feature` | user context | Track a feature usage event |
| POST | `/api/v1/analytics/track-health` | service key | Track a system health metric |
| POST | `/api/v1/analytics/ingestion/events` | user context | Ingest a batch of events via the pipeline |
| POST | `/api/v1/analytics/ingestion/consume` | service key | Drain the Redis stream into the DB |
| GET | `/api/v1/analytics/feature-adoption` | admin | Feature adoption summary (`feature_name`, `days`) |
| GET | `/api/v1/analytics/daily-active-users` | admin | Daily active user counts (`days`) |
| GET | `/api/v1/analytics/system-health` | admin | System health summary (`hours`) |
| GET | `/api/v1/analytics/weekly-report` | admin | Weekly adoption + health report |
| GET | `/api/v1/analytics/anomalies` | admin | Anomaly detection results |
| GET | `/api/v1/analytics/pilot-engagement` | admin | Pilot engagement metrics (`days`) |

### Response contract (backward compatible with monolith)

`GET /api/v1/analytics/events` returns:

```json
[
  {
    "id": "uuid-string",
    "event_type": "page_view",
    "user_id": "uuid-string | null",
    "organization_id": "uuid-string | null",
    "metadata": {},
    "source_service": "prequal-api | null",
    "created_at": "2026-10-02T00:00:00+00:00"
  }
]
```

`POST /api/v1/analytics/track-feature` returns `{"status": "tracked", "event_id": "uuid-string"}` — same shape as the monolith endpoint.

`GET /api/v1/analytics/pilot-engagement` returns the same field set as the monolith (`total_organizations`, `active_organizations_30d`, `total_users` (nullable — resolved cross-service when ORG_SERVICE_URL is configured), `avg_events_per_org`, `onboarding_completion_rate`, `feature_adoption_by_org`, `recently_active_orgs`, `engagement_trends`).

---

## Events

Stream payloads (Redis Streams, field values JSON-encoded where complex):

| Field | Type | Notes |
|-------|------|-------|
| `event_type` | string | `page_view`, `feature_usage`, `onboarding_completion`, `subcontractor_added`, `subcontractor_updated`, `subcontractor_removed`, `cert_uploaded`, `feedback_submitted` |
| `user_id` | string | optional |
| `organization_id` | string | optional |
| `metadata` | JSON string | optional context |
| `source_service` | string | optional emitting service |

---

## Configuration (env)

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | postgres localhost/analytics_service | Service-owned PostgreSQL database |
| `REDIS_URL` | redis://localhost:6379/0 | Event stream broker |
| `ANALYTICS_EVENTS_STREAM` | `analytics:events` | Stream key |
| `ANALYTICS_CONSUMER_GROUP` | `analytics-ingestors` | Consumer group |
| `SERVICE_API_KEY` | none | Required for service auth (fail-closed) |
| `ORG_SERVICE_URL` | none | Optional org name resolution for pilot-engagement |
| `CORS_ALLOWED_ORIGINS` | localhost dev origins | |

---

## Monolith integration (Strangler Fig)

The monolith keeps `/api/analytics/*` routes. When `ANALYTICS_SERVICE_URL` is set, the monolith delegates to this service (with service key + user context headers) and falls back to local implementations when the service is unreachable — preserving backward compatibility and zero-downtime behavior during migration.
