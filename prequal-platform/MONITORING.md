# Prequal Platform - Monitoring & Logging Guide

## Overview

This guide covers the monitoring and logging architecture for the Prequal Subcontractor Compliance Platform.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Application   │────▶│  Structured JSON │────▶│  Log Aggregator │
│   (FastAPI)     │     │     Logs         │     │  (ELK/CloudWatch)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │
        ▼
┌─────────────────┐     ┌──────────────────┐
│  Health Checks  │────▶│   Monitoring     │
│  /health/*      │     │   (Prometheus)   │
└─────────────────┘     └──────────────────┘
```

## Logging

### Configuration

Logging is configured in `app/logging_config.py` with the following features:

- **Structured JSON format** for production environments
- **Multiple log levels** (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Console and file output** support
- **Correlation ID** support for request tracing
- **Sensitive data filtering** for security

### Log Format

Production logs are JSON-formatted:

```json
{
  "timestamp": "2026-05-11T08:00:00.000Z",
  "level": "INFO",
  "logger": "api.main",
  "message": "Request: GET /health",
  "service": "prequal-api",
  "request_id": "abc123"
}
```

### Usage

```python
from app.logging_config import setup_logging, get_logger

# Setup on application start
setup_logging("prequal-api")

# Get logger in modules
logger = get_logger(__name__)

# Log messages
logger.info("User authenticated", extra={"user_id": "123"})
logger.error("Database connection failed", exc_info=True)
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `LOG_FORMAT` | `json` | Output format: `json` or `text` |
| `LOG_FILE` | (none) | Optional file path for log output |

### Log Levels by Environment

| Environment | Level | Format | Notes |
|-------------|-------|--------|-------|
| Development | DEBUG | text | Verbose for debugging |
| Staging | INFO | json | Production-like logging |
| Production | INFO/WARNING | json | Minimize noise, maximize signal |

## Health Checks

The application provides multiple health check endpoints at `/health/*`:

### Endpoints

| Endpoint | Description | Use Case |
|----------|-------------|----------|
| `/health` | Basic health check | Simple uptime monitoring |
| `/health/live` | Liveness probe | Kubernetes restart decision |
| `/health/ready` | Readiness probe | Traffic routing decision |
| `/health/detailed` | Detailed status | Debugging, dashboards |

### Example Responses

**Basic Health Check (`/health`):**
```json
{
  "status": "healthy",
  "timestamp": "2026-05-11T08:00:00.000Z",
  "service": "prequal-api"
}
```

**Readiness Check (`/health/ready`):**
```json
{
  "status": "ready",
  "timestamp": "2026-05-11T08:00:00.000Z",
  "checks": {
    "database": true,
    "redis": true
  }
}
```

**Detailed Health (`/health/detailed`):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-05-11T08:00:00.000Z",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "osha_api": "not_configured"
  },
  "python_version": "3.11.0"
}
```

## Monitoring Stack (Optional ELK)

For centralized log aggregation, the platform supports ELK stack deployment.

### Components

| Component | Port | Purpose |
|-----------|------|---------|
| Elasticsearch | 9200 | Log storage and search |
| Logstash | 5044 | Log processing pipeline |
| Kibana | 5601 | Visualization and dashboards |
| Filebeat | (agent) | Log shipper |

### Setup

```bash
# Deploy ELK stack
docker compose -f docker-compose.logging.yml up -d

# Access Kibana dashboard
open http://localhost:5601
```

### Configuration Files

- `logging/logstash/pipeline/` - Logstash pipeline configuration
- `logging/logstash/logstash.yml` - Logstash settings
- `logging/filebeat/filebeat.yml` - Filebeat log shipper config

## Prometheus Metrics (Future)

The platform can expose Prometheus metrics for monitoring:

### Key Metrics

- **Request rate** - Requests per second
- **Error rate** - Percentage of failed requests
- **Latency** - Response time percentiles (p50, p95, p99)
- **Database connections** - Active/pool size
- **Memory usage** - Heap/non-heap utilization

### Integration

```yaml
# prometheus.yml (example)
scrape_configs:
  - job_name: 'prequal-api'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
```

## Alerting

### Recommended Alerts

| Alert | Condition | Priority | Action |
|-------|-----------|----------|--------|
| Service Down | `/health` returns non-200 for 2 min | Critical | Page on-call |
| High Error Rate | Error rate > 5% for 5 min | High | Investigate logs |
| High Latency | p95 > 2s for 10 min | Medium | Scale or optimize |
| Disk Space | Log volume > 80% | Medium | Clean or expand |
| DB Connection Pool | Pool exhaustion > 80% | High | Investigate queries |

### Alert Channels

- **Critical**: PagerDuty, phone call
- **High**: Slack #alerts, email
- **Medium**: Slack #alerts
- **Low**: Daily digest email

## Log Aggregation Options

### Option 1: ELK Stack (Self-Hosted)

**Pros:**
- Full control over data
- Powerful query language (KQL)
- Rich visualization (Kibana)

**Cons:**
- Resource intensive
- Requires maintenance
- Complex setup

**Best for:** On-premises, data sovereignty requirements

### Option 2: CloudWatch Logs (AWS)

**Pros:**
- Managed service
- Easy integration with AWS
- Pay-per-use pricing

**Cons:**
- Vendor lock-in
- Query costs add up

**Best for:** AWS-native deployments

### Option 3: Datadog/Splunk (SaaS)

**Pros:**
- Fully managed
- Advanced features out of box
- Easy onboarding

**Cons:**
- Expensive at scale
- Data leaves your control

**Best for:** Teams prioritizing convenience over cost

## Dashboard Examples

### Service Health Dashboard

```
Prequal Platform Health
├── API Status
│   ├── Health Check: ✅
│   ├── Response Time (p95): 150ms
│   └── Error Rate: 0.1%
├── Database
│   ├── Connection Pool: 5/20
│   ├── Query Time (avg): 12ms
│   └── Replication Lag: N/A (single instance)
├── Redis
│   ├── Memory: 45MB / 256MB
│   ├── Connected Clients: 3
│   └── Hit Rate: 94%
└── External APIs
    └── OSHA API: ✅
```

### Log Query Examples

**Find all errors in last hour:**
```kql
level: "ERROR" AND @timestamp > now-1h
```

**Track a specific request:**
```kql
request_id: "abc123"
```

**Find slow queries:**
```kql
message: *"Query took"* AND duration_ms > 1000
```

**User activity trail:**
```kql
user_id: "user-123" AND sort:@timestamp asc
```

## Security & Compliance

### Log Redaction

The following fields are automatically redacted from logs:

- Passwords
- API keys
- JWT tokens
- PII (email, SSN, etc.)

### Retention Policy

| Environment | Retention | Storage |
|-------------|-----------|---------|
| Development | 7 days | Local |
| Staging | 30 days | S3/Cloud |
| Production | 90+ days | Compressed archive |

### Access Control

- **Development**: All team members
- **Staging**: Engineering team only
- **Production**: On-call + authorized personnel

## Troubleshooting

### Common Issues

**Logs not appearing:**
1. Check `LOG_LEVEL` environment variable
2. Verify logging handler is configured
3. Check file permissions if writing to file

**Health check failing:**
1. Check database connectivity
2. Verify environment variables are set
3. Review application logs for startup errors

**High log volume:**
1. Reduce log level from DEBUG to INFO
2. Add sampling for high-frequency logs
3. Implement log rotation

## Files Reference

| File | Purpose |
|------|---------|
| `app/logging_config.py` | Logging configuration |
| `api/health.py` | Health check endpoints |
| `docker-compose.logging.yml` | ELK stack compose |
| `api/main.py` | Request logging middleware |

## Next Steps

1. **Implement metrics collection** - Add Prometheus client
2. **Create dashboards** - Build Kibana/Grafana dashboards
3. **Configure alerts** - Set up alerting rules and channels
4. **Log rotation** - Implement log rotation and archival
5. **Distributed tracing** - Add OpenTelemetry for request tracing

---

**Last Updated**: 2026-05-11  
**Maintained By**: DevOps Engineer  
**Related Issues**: [MID-33](/MID/issues/MID-33)
