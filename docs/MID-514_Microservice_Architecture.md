# MID-514: Microservice Architecture Design

**Status**: Draft v1  
**Owner**: Senior Engineer  
**Date**: 2026-07-04  
**Related Issues**: MID-514

---

## 1. Executive Summary

Prequal currently runs as a monolithic FastAPI application serving mid-market general contractors. This document proposes a microservice architecture to support scale, team autonomy, and upcoming feature expansion while maintaining operational stability.

---

## 2. Current State Analysis

### 2.1 Monolith Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── endpoints/    # auth, analytics, subcontractors, compliance, feedback
│   │   ├── router.py    # Central API router
│   │   └── middleware.py
│   ├── services/        # 20+ service modules
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   └── main.py          # FastAPI application
```

### 2.2 Existing Service Inventory

| Service | Type | Bounded Context | External Dependencies |
|---------|------|-----------------|----------------------|
| `auth` | Core | Identity | JWT, sessions |
| `analytics_ingestion` | Core | Analytics | PostgreSQL |
| `analytics_reporting` | Core | Analytics | PostgreSQL |
| `anomaly_detection` | Core | Analytics | PostgreSQL |
| `alert_service` | Core | Notifications | PostgreSQL, notification_service |
| `notification_service` | Core | Notifications | SendGrid, Twilio |
| `billing_service` | Core | Billing | Stripe API |
| `osha_client` | Integration | External Data | OSHA API |
| `state_credential_sync` | Integration | External Data | State licensing boards |
| `external_compliance_pipeline` | Integration | External Data | OSHA, state APIs |
| `data_pipeline` | Integration | External Data | Various |
| `compliance_matching` | Core | Compliance | PostgreSQL |
| `audit_service` | Core | Compliance | PostgreSQL |
| `security_service` | Core | Identity | PostgreSQL |
| `session_manager` | Core | Identity | Redis |
| `pdf_service` | Supporting | Documents | PDF generation |
| `sync_scheduler` | Integration | External Data | Cron/scheduling |

### 2.3 Identified Scaling Boundaries

1. **Analytics Pipeline** - High-volume event ingestion, reporting queries compete with OLTP
2. **External Data Integrations** - OSHA API polling, state credential scrapers, ETL jobs
3. **Alert/Notification System** - Time-sensitive, independent scaling needs
4. **Billing** - Stripe webhook processing, subscription management
5. **Compliance Core** - Primary business logic, should remain stable

---

## 3. Proposed Microservice Architecture

### 3.1 Service Decomposition

```
┌─────────────────────────────────────────────────────────────────────┐
│                           API Gateway                                 │
│                    (Kong/NGINX + Auth Layer)                         │
└────────────────┬─────────────────────────────────────────────────────┘
                 │
       ┌─────────┼──────────┬─────────────┬───────────┬──────────────┐
       │         │          │             │           │              │
       ▼         ▼          ▼             ▼           ▼              ▼
┌──────────┐ ┌────────┐ ┌────────────┐ ┌─────────┐ ┌──────────┐ ┌────────────┐
│  Auth    │ │Compli- │ │  Analytics │ │  Alert  │ │ Billing  │ │ External  │
│  Service │ │  ance  │ │  Service   │ │ Service │ │ Service  │ │  Data      │
│          │ │Service │ │            │ │         │ │          │ │  Service   │
└────┬─────┘ └───┬────┘ └─────┬──────┘ └────┬────┘ └────┬─────┘ └────┬─────┘
     │            │            │             │           │            │
     ▼            ▼            ▼             ▼           ▼            ▼
┌─────────┐  ┌────────┐  ┌───────────┐  ┌────────┐  ┌────────┐  ┌─────────┐
│User/Org │  │Subcon- │  │Feature/   │  │Alerts/ │  │Stripe  │  │OSHA/    │
│ Sessions│  │tractors│  │System     │  │Notifs  │  │Subscrip.│  │State API│
└─────────┘  └────────┘  └───────────┘  └────────┘  └────────┘  └─────────┘
     │            │            │             │           │            │
     └────────────┴────────────┴─────────────┴───────────┴────────────┘
                                  │
                          ┌───────┴───────┐
                          │   PostgreSQL  │
                          │  (Shared DB)  │
                          └───────────────┘
```

### 3.2 Service Definitions

#### 3.2.1 Auth Service

**Responsibility**: Identity, authentication, session management, organization management

**Ownership**: Team Identity

**API Surface**:
- `POST /api/auth/login` - User authentication
- `POST /api/auth/logout` - Session termination
- `POST /api/auth/refresh` - Token refresh
- `GET /api/auth/me` - Current user profile
- `POST /api/auth/register` - User registration
- `GET /api/organizations/{id}` - Organization details
- `POST /api/organizations` - Create organization
- `PATCH /api/organizations/{id}` - Update organization

**Data Ownership**:
- `users` table
- `organizations` table
- `user_sessions` table

**Technology**: FastAPI + Redis (sessions) + PostgreSQL

---

#### 3.2.2 Compliance Service

**Responsibility**: Core subcontractor compliance management - subcontractors, certifications, violations, project assignments

**Ownership**: Team Compliance

**API Surface**:
- `GET/POST /api/subcontractors` - Subcontractor CRUD
- `GET/POST /api/certifications` - Certification management
- `GET /api/compliance/dashboard` - Dashboard data
- `GET /api/compliance/status` - Certification status
- `GET /api/compliance/trends` - Compliance trends
- `GET/POST /api/violations` - Violation tracking
- `GET/POST /api/projects` - Project management
- `POST /api/projects/{id}/subcontractors` - Assign subcontractor

**Data Ownership**:
- `subcontractors` table
- `certifications` table
- `violations` table
- `projects` table
- `project_subcontractors` table

**Technology**: FastAPI + PostgreSQL

---

#### 3.2.3 Analytics Service

**Responsibility**: Feature adoption tracking, system health metrics, weekly reports, anomaly detection

**Ownership**: Team Platform

**API Surface**:
- `POST /api/analytics/track-feature` - Track feature event
- `POST /api/analytics/track-health` - Track system metric
- `GET /api/analytics/feature-adoption` - Feature adoption summary
- `GET /api/analytics/system-health` - System health summary
- `GET /api/analytics/daily-active-users` - DAU metrics
- `GET /api/analytics/weekly-report` - Weekly report
- `GET /api/analytics/anomalies` - Anomaly detection results
- `GET /api/analytics/pilot-engagement` - Pilot customer metrics

**Data Ownership**:
- `analytics_events` table
- `feature_usage_events` table
- `system_health_metrics` table

**Scaling Consideration**: This service should get its own read replica to isolate analytical queries from OLTP workload.

**Technology**: FastAPI + PostgreSQL (read replica) + Redis (caching)

---

#### 3.2.4 Alert Service

**Responsibility**: Certification expiration monitoring, alert scheduling, notification delivery coordination

**Ownership**: Team Notifications

**API Surface**:
- `POST /api/alerts/scan` - Trigger expiration scan
- `GET /api/alerts/summary` - Alert summary
- `POST /api/alerts/deliver` - Process pending alerts
- `GET /api/alerts/notifications/{id}` - Get notification status
- `PATCH /api/alerts/notifications/{id}/acknowledge` - Acknowledge alert

**Data Ownership**:
- `alert_notifications` table
- `alert_preferences` table
- `certification_renewals` table

**External Dependencies**:
- Notification Service (for actual delivery)
- Compliance Service (for certification data)

**Technology**: FastAPI + PostgreSQL + Celery (background jobs) + Redis (queue)

---

#### 3.2.5 Notification Service

**Responsibility**: Email and SMS delivery via SendGrid/Twilio

**Ownership**: Team Notifications

**API Surface**:
- `POST /api/notifications/email` - Send email
- `POST /api/notifications/sms` - Send SMS
- `GET /api/notifications/{id}/status` - Delivery status
- `POST /api/notifications/webhook/sendgrid` - SendGrid webhooks
- `POST /api/notifications/webhook/twilio` - Twilio webhooks

**Data Ownership**:
- `notification_delivery_logs` table

**Technology**: FastAPI + SendGrid + Twilio + PostgreSQL

---

#### 3.2.6 Billing Service

**Responsibility**: Stripe subscription management, checkout, billing portal

**Ownership**: Team Revenue

**API Surface**:
- `POST /api/billing/customer` - Create Stripe customer
- `POST /api/billing/subscription` - Create subscription
- `GET /api/billing/subscription/{id}` - Get subscription
- `DELETE /api/billing/subscription/{id}` - Cancel subscription
- `POST /api/billing/checkout` - Create checkout session
- `POST /api/billing/portal` - Create billing portal session
- `POST /api/billing/webhook` - Stripe webhooks

**Data Ownership**:
- Owns Stripe customer_id mapping
- Reads `organizations` table for plan limits
- Reads `subcontractors` table for usage

**Technology**: FastAPI + Stripe API + PostgreSQL

---

#### 3.2.7 External Data Service

**Responsibility**: OSHA API ingestion, state credential scraping, external compliance data pipelines

**Ownership**: Team Data

**API Surface**:
- `POST /api/external/osha/sync` - Trigger OSHA sync
- `GET /api/external/osha/status` - Sync status
- `POST /api/external/state-credentials/sync` - Trigger state sync
- `GET /api/external/state-credentials/sources` - Available sources
- `GET /api/external/sync/logs` - Sync history
- `GET /api/external/freshness` - Data freshness status

**Data Ownership**:
- `osha_inspections` table
- `state_credential_records` table
- `sync_run_logs` table
- `osha_data_freshness` table

**Technology**: FastAPI + Celery (async jobs) + PostgreSQL + aiohttp (external APIs)

---

### 3.3 Supporting Infrastructure

#### 3.3.1 API Gateway

**Technology**: Kong or NGINX with Lua scripting

**Responsibilities**:
- Request routing to services
- Authentication/authorization (JWT validation)
- Rate limiting
- Request/response logging
- SSL termination

**Routing Rules**:
```
/api/auth/*           → Auth Service (:8001)
/api/subcontra*       → Compliance Service (:8002)
/api/compliance/*     → Compliance Service (:8002)
/api/certifications/* → Compliance Service (:8002)
/api/analytics/*      → Analytics Service (:8003)
/api/alerts/*         → Alert Service (:8004)
/api/notifications/*  → Notification Service (:8005)
/api/billing/*        → Billing Service (:8006)
/api/external/*       → External Data Service (:8007)
```

#### 3.3.2 Service Mesh

**Technology**: Kubernetes + Istio (or Linkerd for simplicity)

**Benefits**:
- mTLS between services
- Traffic management
- Observability (distributed tracing)
- Circuit breaking

#### 3.3.3 Event Bus

**Technology**: Redis Streams or Apache Kafka

**Use Cases**:
- Async communication between services
- Event-driven alerts trigger
- Analytics event ingestion decoupling
- Cross-service data consistency

**Event Schema Example**:
```json
{
  "event_type": "certification.expiring",
  "timestamp": "2026-07-04T10:00:00Z",
  "payload": {
    "certification_id": "uuid",
    "subcontractor_id": "uuid",
    "expires_at": "2026-07-15"
  }
}
```

---

## 4. Data Architecture

### 4.1 Database Strategy

**Option A: Shared Database (Recommended for Prequal scale)**

Single PostgreSQL database with schemas per service:

```
prequal_db
├── auth_schema
│   ├── users
│   ├── organizations
│   └── user_sessions
├── compliance_schema
│   ├── subcontractors
│   ├── certifications
│   ├── violations
│   └── projects
├── analytics_schema
│   ├── analytics_events
│   ├── feature_usage_events
│   └── system_health_metrics
├── alerts_schema
│   ├── alert_notifications
│   └── alert_preferences
├── billing_schema
│   └── (Stripe mapping tables)
├── external_schema
│   ├── osha_inspections
│   ├── state_credential_records
│   └── sync_run_logs
└── shared_schema
    ├── audit_logs
    └── notification_delivery_logs
```

**Benefits**: Simplified operations, transactions across services, cost-effective

**Option B: Database-per-Service (Future Scale)**

For when team autonomy and scaling independently become critical.

### 4.2 Data Ownership Rules

| Service | Owns | Reads From |
|---------|------|-----------|
| Auth | users, organizations, sessions | - |
| Compliance | subcontractors, certifications, violations, projects | organizations (read) |
| Analytics | analytics_events, feature_usage_events | organizations (read) |
| Alert | alert_notifications, alert_preferences | certifications (read), subcontractors (read) |
| Notification | notification_delivery_logs | - |
| Billing | stripe_customer_mapping | organizations (read), subcontractors (count) |
| External Data | osha_inspections, state_credential_records, sync_run_logs | subcontractors (for matching) |

---

## 5. Migration Strategy

### Phase 1: Extract Analytics Service (MID-515)
1. Create new `analytics-service` repository
2. Move analytics endpoints and models
3. Set up read replica for analytics queries
4. Run both services in parallel
5. Switch reads to new service
6. Decommission old analytics code

### Phase 2: Extract External Data Service (MID-516)
1. Create new `external-data-service` repository
2. Move OSHA client, state credential sync, ETL pipelines
3. Expose async job status API
4. Update Compliance Service to use async calls
5. Decomcommission old integration code

### Phase 3: Extract Alert/Notification Services (MID-517)
1. Split alerts and notifications into separate services
2. Implement event bus for async communication
3. Add Celery for background job processing
4. Update Compliance Service event publishing

### Phase 4: Extract Billing Service (MID-518)
1. Create billing service with Stripe integration
2. Add webhook endpoints
3. Migrate subscription logic
4. Add usage-based limit enforcement

### Phase 5: API Gateway + Mesh (MID-519)
1. Deploy Kong/NGINX
2. Set up authentication middleware
3. Configure routing rules
4. Implement rate limiting
5. Add distributed tracing

---

## 6. API Contracts

### 6.1 Internal Service Communication

Services communicate via:
1. **Synchronous (REST)**: For request-response patterns
2. **Asynchronous (Events)**: For decoupled, eventual-consistency patterns

### 6.2 Event Contracts

```python
# Certification Expiration Event
{
    "event": "certification.expiring",
    "service": "compliance",
    "data": {
        "certification_id": "uuid",
        "subcontractor_id": "uuid",
        "organization_id": "uuid",
        "expires_at": "ISO8601",
        "days_until": 14
    }
}

# Alert Created Event
{
    "event": "alert.created",
    "service": "alerts",
    "data": {
        "alert_id": "uuid",
        "certification_id": "uuid",
        "alert_type": "expiration_14d",
        "scheduled_for": "ISO8601"
    }
}

# Notification Sent Event
{
    "event": "notification.sent",
    "service": "notifications",
    "data": {
        "notification_id": "uuid",
        "alert_id": "uuid",
        "method": "email",
        "recipient": "user@example.com",
        "success": true
    }
}
```

---

## 7. Observability

### 7.1 Distributed Tracing

**Technology**: Jaeger or Tempo (Grafana)

Each request gets a trace ID propagated via HTTP headers:
```
X-Trace-ID: abc123
X-Span-ID: def456
```

### 7.2 Logging

**Technology**: ELK Stack or Loki

Standard log format:
```json
{
  "timestamp": "ISO8601",
  "level": "INFO",
  "service": "compliance-service",
  "trace_id": "abc123",
  "message": "Certification verified",
  "context": {
    "certification_id": "uuid",
    "subcontractor_id": "uuid"
  }
}
```

### 7.3 Metrics

**Technology**: Prometheus + Grafana

Key metrics per service:
- Request rate
- Error rate
- Latency (p50, p95, p99)
- Queue depth (for async services)
- Database connection pool usage

---

## 8. Security Considerations

### 8.1 Service-to-Service Authentication

- mTLS via Istio service mesh
- Service accounts with rotated credentials
- API keys for legacy integrations

### 8.2 Data Isolation

- Row-level security in PostgreSQL
- Organization ID filtering mandatory on all queries
- Audit logging on sensitive operations

### 8.3 API Security

- Rate limiting per service
- JWT validation at gateway
- Input validation with Pydantic
- SQL injection prevention via ORM

---

## 9. Deployment Architecture

### 9.1 Kubernetes Manifest Structure

```
kubernetes/
├── base/
│   ├── namespace.yaml
│   ├── services/
│   │   ├── auth-deployment.yaml
│   │   ├── compliance-deployment.yaml
│   │   ├── analytics-deployment.yaml
│   │   ├── alert-deployment.yaml
│   │   ├── notification-deployment.yaml
│   │   ├── billing-deployment.yaml
│   │   └── external-data-deployment.yaml
│   └── gateway/
│       ├── kong-deployment.yaml
│       └── ingress.yaml
└── overlays/
    ├── staging/
    └── production/
```

### 9.2 Resource Recommendations

| Service | Replicas | CPU | Memory |
|---------|----------|-----|--------|
| Auth | 2-3 | 500m | 512Mi |
| Compliance | 3-5 | 1000m | 1Gi |
| Analytics | 2-4 | 1000m | 1Gi |
| Alert | 2-3 | 500m | 512Mi |
| Notification | 2-3 | 500m | 512Mi |
| Billing | 1-2 | 500m | 512Mi |
| External Data | 2-4 | 1000m | 1Gi |

---

## 10. Open Questions

1. **Database strategy**: Shared DB with schemas vs. separate DBs per service?
2. **Event bus technology**: Redis Streams vs. Kafka?
3. **Auth propagation**: JWT vs. session-based across services?
4. **Contract testing**: Who owns API contract definitions?

---

## 11. Next Steps

- [ ] Review architecture with CTO/CEO
- [ ] Prioritize service extraction order based on team capacity
- [ ] Create detailed migration runbooks for Phase 1
- [ ] Update project board with microservice epics

---

## Appendix A: Technology Stack Summary

| Component | Current | Proposed |
|-----------|---------|----------|
| API Gateway | None | Kong/NGINX |
| Backend Framework | FastAPI (monolith) | FastAPI (per service) |
| Database | PostgreSQL (shared) | PostgreSQL (shared schema) |
| Cache | Redis | Redis |
| Message Queue | None | Redis Streams / Kafka |
| Container Orchestration | Docker Compose | Kubernetes |
| Service Mesh | None | Istio/Linkerd |
| Tracing | None | Jaeger/Tempo |
| Metrics | None | Prometheus + Grafana |
| CI/CD | GitHub Actions | GitHub Actions (per repo) |