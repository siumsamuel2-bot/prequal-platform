# ADR-001: Microservice Architecture for Prequal Platform

**Date:** 2026-07-04
**Status:** Accepted
**Decider:** CTO

---

## Context

Prequal is a subcontractor compliance platform for mid-market general contractors. The current system is a FastAPI monolith handling:

- Identity & access management (auth, sessions, users)
- Organization management
- Subcontractor lifecycle (add, update, remove subcontractors)
- Certification tracking & document management
- State credential verification (Texas TDLR, OSHA, etc.)
- Compliance alerting & reporting
- Analytics pipeline (events, ingestion, reporting)
- Feedback collection

As the platform scales, the monolith presents challenges:
- **Deployment coupling** - one service must be redeployed for any change
- **Scalability limits** - analytics/ingestion workloads differ from API workloads
- **Team topology** - different teams need independent ownership
- **Reliability blast radius** - one service failure can cascade

This ADR defines the target microservice architecture for the Prequal platform.

---

## Decision

### Service Decomposition

The platform will be decomposed into the following services:

| Service | Responsibility | Key Data | Communication |
|---------|----------------|----------|---------------|
| **identity-service** | User authentication, session management, RBAC | users, user_sessions | Sync REST |
| **organization-service** | Organization CRUD, user-org linkage, tenant context | organizations | Sync REST, Events |
| **subcontractor-service** | Subcontractor lifecycle, certification management | subcontractors, certifications | Sync REST, Events |
| **compliance-service** | Credential verification orchestration, compliance rules engine | state_credential_records, osha_inspections, violations | Sync REST, Async Events |
| **integration-service** | External API sync (TDLR, OSHA, SILTRA), sync job orchestration | sync_run_logs | Async messaging (internal) |
| **analytics-service** | Event ingestion, reporting queries, anomaly detection | analytics_events | Async ingestion endpoint |
| **notification-service** | Email alerts, certification expiration, compliance alerts | notification_queue | Async via queue |
| **feedback-service** | Feedback collection and aggregation | feedback | Sync REST |

### API Gateway

A single **API Gateway** (`gateway-service`) acts as the entry point:
- Routes requests to appropriate backend services
- Handles cross-cutting concerns (auth token validation, rate limiting, request logging)
- Exposes the public REST API to frontend clients
- Implementations: Kong, AWS API Gateway, or self-hosted (FastAPI +nginx)

### Service-to-Service Communication

**Synchronous (Request-Response):**
- Service-to-service REST calls for query operations requiring immediate response
- Internal service mesh for service discovery (Consul, etcd, or Kubernetes DNS)

**Asynchronous (Event-Driven):**
- **Message Broker:** RabbitMQ or AWS SQS/SNS
- Event patterns:
  - `SubcontractorCreated`, `SubcontractorUpdated`, `CertificationUploaded`
  - `CredentialVerified`, `ComplianceStatusChanged`
  - `CertificationExpiring` (90-day alert)

### Data Architecture

**Database per Service:**
- Each service owns its relational data in PostgreSQL
- Shared nothing principle - services never share database connections

**Cross-service data needs handled via:**
- API calls for real-time queries
- Eventual consistency via event log replication
- Read replicas for analytics queries

**Event Store:**
- `integration-service` maintains sync state
- `analytics-service` maintains event store

### Technology Stack

| Component | Technology |
|-----------|------------|
| API Gateway | Kong or FastAPI + nginx |
| Services | Python 3.11+ / FastAPI |
| Message Broker | RabbitMQ |
| Service Mesh | Kubernetes (EKS) or Docker Compose |
| Database | PostgreSQL 15+ (RDS or self-hosted) |
| Cache | Redis (session store, rate limiting) |
| Object Storage | S3 (document uploads) |
| Observability | Prometheus + Grafana + Jaeger |

### Deployment Model

**Containers:** Each service containerized (Docker)
**Orchestration:** Kubernetes (EKS) for production, Docker Compose for local dev
**CI/CD:** GitHub Actions per repo (separate repo per service)

---

## Consequences

### Positive

1. Independent deployment - teams ship features without coordination
2. Targeted scaling - analytics can scale independently from API
3. Failure isolation - compliance outage doesn't affect feedback
4. Technology flexibility - services can adopt new tech independently
5. Team autonomy - clear ownership boundaries

### Negative

1. **Operational complexity** - distributed tracing, service discovery, deployment coordination
2. **Data consistency** - eventual consistency requires rethinking workflows
3. **Testing complexity** - integration tests span services
4. **Latency** - network calls replace in-memory calls
5. **Initial development velocity** - scaffolding overhead for new services

### Mitigations

- Adopt **Backends for Frontends** pattern to aggregate service calls
- Use **Circuit Breakers** (PyBreaker) for graceful degradation
- Implement **Saga pattern** for distributed transactions where needed
- Invest in **local development environment** (Docker Compose full stack)

---

## Migration Strategy

### Phase 1: Strangler Fig (Months 1-3)
1. Deploy API Gateway in front of existing monolith
2. Extract `identity-service` first (most stable, lowest change rate)
3. Route only new auth traffic through extracted service

### Phase 2: Service Extraction (Months 3-6)
1. Extract `analytics-service` (separate ingestion pipeline)
2. Extract `integration-service` (sync jobs are decoupled)
3. Extract `subcontractor-service`

### Phase 3: Domain Services (Months 6-9)
1. Extract `compliance-service`
2. Extract `organization-service`
3. Extract remaining services

### Phase 4: Gateway-Only (Month 9+)
1. Remove monolith
2. Gateway routes 100% to microservices

---

## Alternatives Considered

### 1. Modular Monolith
Keep single deployable unit but enforce strict module boundaries.
- **Rejected** - does not solve deployment coupling or scaling issues

### 2. Event-Driven Only (Kafka)
Use event sourcing for all state changes.
- **Rejected** - higher complexity, eventual consistency harder to reason about for this domain

### 3. Serverless (AWS Lambda)
Each function as a separate deployable.
- **Rejected** - cold start latency, vendor lock-in concerns

---

## Notes

- This ADR will be revisited after Phase 1 completion
- Service boundaries may shift based on operational learnings
- Cost analysis required before finalizing Kubernetes vs ECS