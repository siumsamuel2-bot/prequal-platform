# Implementation Task Breakdown - Microservice Migration

**Based on:** ADR-001 Microservice Architecture
**Created:** 2026-07-04
**Priority:** High

---

## Phase 1: Foundation (Weeks 1-4)

### Infrastructure Setup

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-001 | Set up Kubernetes cluster (EKS) with namespaces | DevOps | 16 | AWS account |
| T-002 | Configure PostgreSQL RDS instances (1 per service) | DevOps | 8 | T-001 |
| T-003 | Set up RabbitMQ cluster | DevOps | 8 | T-001 |
| T-004 | Configure Redis (ElastiCache) | DevOps | 4 | T-001 |
| T-005 | Set up S3 bucket for document storage | DevOps | 2 | T-001 |
| T-006 | Configure ingress controller (nginx) | DevOps | 4 | T-001 |
| T-007 | Set up service mesh/SDK (Consul or Kubernetes DNS) | DevOps | 8 | T-001, T-002 |

### API Gateway

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-010 | Deploy Kong API Gateway | DevOps | 8 | T-001, T-006 |
| T-011 | Configure routes for monolith | DevOps | 4 | T-010 |
| T-012 | Implement auth token validation middleware | Backend | 8 | T-010 |
| T-013 | Configure rate limiting | DevOps | 4 | T-010 |

### Observability

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-020 | Deploy Prometheus + Grafana stack | DevOps | 12 | T-001 |
| T-021 | Configure distributed tracing (Jaeger) | DevOps | 8 | T-001 |
| T-022 | Set up centralized logging (ELK or Loki) | DevOps | 12 | T-001 |
| T-023 | Create service health check endpoints | Backend | 4 | All services |

---

## Phase 2: First Service Extraction - Identity (Weeks 5-8)

### identity-service

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-030 | Create identity-service repo structure | Backend | 4 | None |
| T-031 | Implement User model + CRUD endpoints | Backend | 12 | T-007 |
| T-032 | Implement session management (Redis) | Backend | 12 | T-004 |
| T-033 | Implement JWT/Rotation token logic | Backend | 16 | T-032 |
| T-034 | Write unit tests for identity-service | Backend | 16 | T-031, T-032, T-033 |
| T-035 | Create Docker container + Helm chart | DevOps | 8 | T-030 |
| T-036 | Deploy identity-service to staging | DevOps | 4 | T-035, T-001 |
| T-037 | Migrate auth traffic to identity-service | Backend | 8 | T-036 |
| T-038 | Run parallel load test | QA | 8 | T-037 |

---

## Phase 3: Analytics Service Extraction (Weeks 9-12)

### analytics-service

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-040 | Create analytics-service repo | Backend | 4 | None |
| T-041 | Implement event ingestion endpoint | Backend | 12 | T-007 |
| T-042 | Implement event storage (PostgreSQL) | Backend | 8 | T-007 |
| T-043 | Implement analytics_ingestion.py logic | Backend | 16 | T-042 |
| T-044 | Implement analytics_reporting.py queries | Backend | 16 | T-042 |
| T-045 | Implement anomaly_detection.py | Backend | 12 | T-042 |
| T-046 | Write unit tests | Backend | 16 | T-041-T-045 |
| T-047 | Containerize + deploy to staging | DevOps | 8 | T-040 |
| T-048 | Set up async event consumers | Backend | 12 | T-003, T-047 |

---

## Phase 4: Integration Service Extraction (Weeks 13-16)

### integration-service

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-050 | Create integration-service repo | Backend | 4 | None |
| T-051 | Implement sync_scheduler.py | Backend | 12 | T-007 |
| T-052 | Implement state_credential_sync logic | Backend | 16 | T-007 |
| T-053 | Implement Texas TDLR client (texas_tdlr.py) | Backend | 12 | T-007 |
| T-054 | Implement OSHA API client | Backend | 12 | External API |
| T-055 | Implement SILTRA client | Backend | 12 | External API |
| T-056 | Write unit tests | Backend | 16 | T-051-T-055 |
| T-057 | Containerize + deploy to staging | DevOps | 8 | T-050 |
| T-058 | Configure sync job scheduling (Celery or similar) | Backend | 8 | T-057 |

---

## Phase 5: Subcontractor Service Extraction (Weeks 17-20)

### subcontractor-service

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-060 | Create subcontractor-service repo | Backend | 4 | None |
| T-061 | Implement Subcontractor model + CRUD | Backend | 12 | T-007 |
| T-062 | Implement Certification model + CRUD | Backend | 12 | T-061 |
| T-063 | Implement document upload to S3 | Backend | 8 | T-005, T-061 |
| T-064 | Implement event publishing (MQ) | Backend | 8 | T-003 |
| T-065 | Write unit tests | Backend | 16 | T-061-T-064 |
| T-066 | Containerize + deploy to staging | DevOps | 8 | T-060 |
| T-067 | Configure BFF aggregation | Backend | 12 | T-060, T-066 |

---

## Phase 6: Remaining Services (Weeks 21-28)

### organization-service

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-070 | Extract organization endpoints | Backend | 12 | T-007 |
| T-071 | Implement org-user linking | Backend | 8 | T-070 |
| T-072 | Containerize + deploy | DevOps | 8 | T-070 |
| T-073 | Write tests | Backend | 12 | T-070-T-072 |

### compliance-service

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-080 | Extract compliance endpoints | Backend | 12 | T-007 |
| T-081 | Implement state_credential_records logic | Backend | 16 | T-080 |
| T-082 | Implement OSHA data handling | Backend | 12 | T-080 |
| T-083 | Implement compliance rules engine | Backend | 16 | T-082 |
| T-084 | Implement MQ consumers for sync events | Backend | 12 | T-003 |
| T-085 | Write tests | Backend | 16 | T-080-T-084 |
| T-086 | Containerize + deploy | DevOps | 8 | T-080 |

### notification-service

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-090 | Create notification-service repo | Backend | 4 | None |
| T-091 | Implement email sending (SES/SendGrid) | Backend | 8 | T-007 |
| T-092 | Implement expiration alert logic | Backend | 12 | T-090 |
| T-093 | Implement MQ consumers | Backend | 8 | T-003 |
| T-094 | Containerize + deploy | DevOps | 6 | T-090 |

### feedback-service

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-100 | Extract feedback endpoints | Backend | 8 | T-007 |
| T-101 | Containerize + deploy | DevOps | 6 | T-100 |

---

## Phase 7: Monolith Sunset (Weeks 29-32)

| Task | Description | Owner | Estimated Hours | Dependencies |
|------|-------------|-------|-----------------|--------------|
| T-110 | Update gateway routes to 100% microservices | DevOps | 8 | All services deployed |
| T-111 | Run full integration test suite | QA | 16 | T-110 |
| T-112 | Decommission monolith | DevOps | 4 | T-111 |
| T-113 | Final load test + performance validation | QA | 16 | T-112 |
| T-114 | Update documentation + runbooks | Backend | 8 | T-113 |

---

## Resource Summary

| Role | Total Hours |
|------|-------------|
| Backend | ~320 |
| DevOps | ~140 |
| QA | ~48 |
| **Total** | **~508** |

---

## Recommended Child Issues

| Issue | Title | Phase | Priority |
|-------|-------|-------|----------|
| MID-515 | Infrastructure: Set up Kubernetes cluster and namespaces | Phase 1 | P0 |
| MID-516 | Infrastructure: Configure PostgreSQL RDS instances | Phase 1 | P0 |
| MID-517 | Infrastructure: Deploy RabbitMQ cluster | Phase 1 | P0 |
| MID-518 | API Gateway: Deploy and configure Kong | Phase 1 | P0 |
| MID-519 | Observability: Deploy Prometheus/Grafana/Jaeger | Phase 1 | P1 |
| MID-520 | Extract identity-service from monolith | Phase 2 | P0 |
| MID-521 | Extract analytics-service from monolith | Phase 3 | P1 |
| MID-522 | Extract integration-service from monolith | Phase 4 | P1 |
| MID-523 | Extract subcontractor-service from monolith | Phase 5 | P1 |
| MID-524 | Extract compliance-service from monolith | Phase 6 | P2 |
| MID-525 | Sunsetting monolith - final cutover | Phase 7 | P2 |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data migration complexity | Medium | High | Phase 1-2 focus on new data; monolith remains for existing |
| Service discovery issues | Medium | Medium | Invest in observability early |
| Network latency (sync calls) | High | Medium | Use async where possible; cache aggressively |
| Team unfamiliarity with k8s | High | Medium | Dedicate 1 week to k8s training in Phase 1 |
| External API rate limits (TDLR/OSHA) | Medium | Low | Implement retry with backoff; queue jobs |

---

## Definition of Done

- [ ] All 8 services deployed independently
- [ ] API Gateway routing 100% to microservices
- [ ] Monolith decommissioned
- [ ] All services pass integration test suite
- [ ] P99 latency < 200ms for API calls
- [ ] Zero data loss during migration
- [ ] Documentation updated (ADR, runbooks, API docs)