# Monitoring Metrics Reference

This document describes the metrics exposed by the Prequal Platform for monitoring and alerting.

## Infrastructure Metrics

These metrics are automatically collected by Prometheus from the infrastructure components.

### System Metrics (Node Exporter)
- `node_cpu_seconds_total` - CPU usage by mode
- `node_memory_MemTotal_bytes` - Total memory
- `node_memory_MemAvailable_bytes` - Available memory
- `node_filesystem_size_bytes` - Disk size
- `node_filesystem_free_bytes` - Free disk space

### Container Metrics (cAdvisor)
- `container_memory_usage_bytes` - Container memory usage
- `container_cpu_usage_seconds_total` - Container CPU usage
- `container_spec_memory_limit_bytes` - Container memory limit

### Application Metrics (Backend)
- `up` - Service availability (1 = up, 0 = down)
- `http_requests_total` - Total HTTP requests (labels: method, status, endpoint)
- `http_request_duration_seconds_bucket` - Request latency histogram
- `http_request_duration_seconds_count` - Request latency count
- `http_request_duration_seconds_sum` - Request latency sum
- `db_pool_active_connections` - Active database connections
- `db_pool_max_connections` - Maximum database connections
- `db_pool_idle_connections` - Idle database connections

## Business Metrics

These metrics should be exposed by the application to track business-level KPIs.

### Subcontractor Metrics
- `subcontractors_total` - Total number of registered subcontractors
- `subcontractors_active` - Number of active subcontractors (working on projects)
- `subcontractors_onboarded_total` - Total subcontractors onboarded (counter)

### Certification Metrics
- `certifications_total` - Total certifications in system
- `certifications_valid` - Certifications currently valid
- `certifications_expiring_soon` - Certifications expiring within 30 days
- `certifications_expired` - Certifications that have expired
- `certifications_verified_total` - Certifications verified against state databases
- `certifications_rejected_total` - Certifications rejected during verification

### Compliance Metrics
- `compliance_rate` - Percentage of subcontractors in compliance (0-100)
- `osha_violations_total` - Total OSHA violations tracked
- `osha_violations_critical` - Critical OSHA violations
- `safety_checks_completed_total` - Total safety checks completed
- `safety_checks_failed_total` - Safety checks that failed

### Alert Metrics
- `alerts_total` - Total alerts generated (counter)
- `alerts_acknowledged_total` - Alerts acknowledged by users
- `alerts_expired_total` - Alerts that expired without action

## Exposing Custom Metrics

The FastAPI backend uses Prometheus client library to expose custom metrics. Example:

```python
from prometheus_client import Counter, Gauge, Histogram

# Counter for total subcontractors onboarded
subcontractors_onboarded = Counter(
    'subcontractors_onboarded_total',
    'Total number of subcontractors onboarded'
)

# Gauge for current compliance rate
compliance_rate = Gauge(
    'compliance_rate',
    'Current compliance rate percentage'
)

# Histogram for certification verification latency
certification_verification_latency = Histogram(
    'certification_verification_seconds',
    'Time spent verifying certifications'
)
```

## Alerting Thresholds

### Production Environment
| Alert | Threshold | Severity |
|-------|-----------|----------|
| Service Down | 2m | Critical |
| Error Rate | >5% for 5m | High |
| Latency p95 | >500ms for 5m | Medium |
| DB Pool | >80% for 5m | High |
| Disk Space | >80% for 10m | Medium |
| Memory Pressure | >90% for 5m | High |

### Staging Environment
| Alert | Threshold | Severity |
|-------|-----------|----------|
| Service Down | 5m | Warning |
| Error Rate | >10% for 10m | Warning |
| Latency p95 | >1s for 10m | Warning |
| DB Pool | >70% for 10m | Warning |

## Dashboards

### Production Dashboard
- Service health status
- SLO error budget tracking
- Request rates and error rates
- Database connection pool
- System resources
- **Business metrics**: certification compliance, subcontractor tracking

### Staging Dashboard
- Staging service health
- Staging-specific metrics
- Deployment pipeline status
- Resource usage for staging containers

## Runbooks

When alerts fire, consult the incident response runbook:
- [Incident Response Plan](./docs/INCIDENT_RESPONSE_PLAN.md)
- [Deployment Runbook](./docs/DEPLOYMENT_RUNBOOK.md)