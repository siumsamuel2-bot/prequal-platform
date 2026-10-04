# Prequal Platform - Monitoring & Logging Guide

## Overview

This guide covers the monitoring and logging setup for the Prequal compliance platform.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Application    │────▶│  Promtail        │────▶│  Loki           │────▶│  Grafana        │
│  (FastAPI)      │     │  (log shipper)   │     │  (log store)    │     │  (dashboards)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘     └─────────────────┘
        │                                                ▲
        ▼                                                │
┌─────────────────┐     ┌──────────────────┐             │
│  Health Checks  │     │  Metrics         │─────────────┘
│  /health/*      │     │  (Prometheus)    │
└─────────────────┘     └──────────────────┘
```

## Logging

### Configuration

Logging is configured in `app/logging_config.py` with the following features:

- **Structured JSON logs** for production
- **Environment-based log levels** (DEBUG, INFO, WARNING, ERROR)
- **Correlation IDs** for request tracing
- **Sensitive data filtering**

### Log Levels

| Level | When to Use |
|-------|-------------|
| DEBUG | Detailed debugging information |
| INFO | General operational messages |
| WARNING | Unexpected but handled situations |
| ERROR | Errors that need attention |
| CRITICAL | Severe errors requiring immediate action |

### Usage Example

```python
from app.logging_config import get_logger

logger = get_logger(__name__)

# Simple logging
logger.info("User logged in", extra={"extra_fields": {"user_id": user_id}})
logger.error("Database connection failed", exc_info=True)

# With request context
logger.info("Processing request", extra={
    "request_id": request_id,
    "user_id": user_id
})
```

### Log Output

**Development (text format):**
```
2026-05-11 12:00:00,000 - app.main - INFO - Starting up Prequal API
2026-05-11 12:00:01,000 - app.main - INFO - Database connection established
```

**Production (JSON format):**
```json
{
  "timestamp": "2026-05-11T12:00:00.000Z",
  "level": "INFO",
  "logger": "app.main",
  "message": "Starting up Prequal API",
  "service": "prequal-api"
}
```

## Health Checks

### Endpoints

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `/health` | Basic uptime check | 200 if running |
| `/health/live` | Liveness probe | 200 if responsive |
| `/health/ready` | Readiness probe | 200 if ready for traffic |
| `/health/detailed` | Full status | Detailed service health |

### Example Responses

**Basic Health:**
```json
{
  "status": "healthy",
  "timestamp": "2026-05-11T12:00:00.000Z",
  "service": "prequal-api"
}
```

**Detailed Health:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-05-11T12:00:00.000Z",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "osha_api": "not_configured"
  },
  "python_version": "3.11.0"
}
```

## Log Aggregation

### Development - Console Logs

For local development, logs output to console:

```bash
docker-compose -f docker-compose.staging.yml logs -f backend
```

### Production - Loki + Grafana + Promtail

Production uses the Loki stack defined in `docker-compose.monitoring.yml` (combined with Prometheus/Grafana for metrics):

```bash
# Start the full monitoring stack (Prometheus, Grafana, Loki, Promtail, node-exporter, cAdvisor)
docker-compose -f docker-compose.monitoring.yml up -d

# Access Grafana
open http://localhost:3000

# Query Loki logs
curl "http://localhost:3100/loki/api/v1/query_range?query=%7Bjob%3D%22prequal-app%22%7D"
```

### How Log Shipping Works

1. **Application**: the FastAPI API emits structured JSON logs (timestamp, level, message, request_id) to stdout and/or `LOG_FILE`
2. **Docker**: services use the `json-file` logging driver (configured in `docker-compose.prod.yml`)
3. **Promtail**: discovers containers via the Docker socket (`docker_sd_configs`) and ships their stdout logs to Loki. Docker-discovered logs are labeled `job=prequal-app` plus `service`/`container`/`logstream` via relabel rules. Logs written to `LOG_FILE` (mounted at `./logs`) are picked up by the `application` scrape job.
4. **Loki**: stores and indexes logs by label (port 3100, config in `monitoring/local-config.yaml`)
5. **Grafana**: Loki datasource is provisioned via `monitoring/grafana-datasources.yml`; dashboards are provisioned via `monitoring/grafana-dashboards-provider.yml` + the dashboard JSONs

### LogQL Examples

```logql
# All application logs
{job="prequal-app"}

# Errors only
{job="prequal-app"} | json | level="ERROR"

# Logs for a specific request ID
{job="prequal-app"} | json | request_id="<uuid>"

# Error rate over 24h
sum(count_over_time({job="prequal-app"} | json | level="ERROR" [24h]))
```

## Request Logging

All HTTP requests are automatically logged:

```python
# Middleware captures:
# - Method
# - Path
# - Status code
# - Response time (optional)
# - Request ID (if present)
```

## Monitoring Checklist

### Before Deployment

- [ ] Set appropriate log level (INFO for staging, WARNING for production)
- [ ] Configure log retention policy
- [ ] Set up log backup/export
- [ ] Test health check endpoints
- [ ] Configure alerting on errors

### Ongoing

- [ ] Review error logs daily
- [ ] Monitor health check dashboards
- [ ] Track response time trends
- [ ] Review and rotate logs
- [ ] Update documentation

## Troubleshooting

### No Logs Appearing

```bash
# Check log level
docker-compose logs backend | grep "LOG_LEVEL"

# Verify logging configuration
curl http://localhost:8000/health
```

### Health Check Failing

```bash
# Check individual components
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/detailed

# Check backend logs
docker-compose logs -f backend
```

### High Error Rate

```bash
# Filter error logs
docker-compose logs backend | grep "ERROR"

# Check recent errors only
docker-compose logs --since=1h backend | grep "ERROR"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FORMAT` | Output format (json/text) | `json` |
| `LOG_FILE` | Optional log file path | - |

## Security Considerations

### Log Security

- Never log sensitive data (passwords, tokens, PII)
- Use appropriate log levels to avoid data leakage
- Implement log rotation to prevent disk exhaustion
- Secure log storage access

### Health Check Security

- Health endpoints should not expose sensitive info
- Rate limit health check endpoints
- Consider authentication for detailed health
- Use network policies to restrict access

## Dashboards

Grafana dashboards are provisioned automatically when the monitoring stack starts:

| Dashboard | File | Panels |
|-----------|------|--------|
| Prequal API (prod) | `monitoring/grafana-dashboard.json` | Error rates, latency, request counts, resource usage — real-time and 24h views |
| Prequal Staging | `monitoring/grafana-staging-dashboard.json` | Staging environment views |
| Analytics | `monitoring/grafana-analytics-dashboard.json` | Analytics service views |

Dashboards load from `/etc/grafana/provisioning/dashboards/` via the provider in `monitoring/grafana-dashboards-provider.yml` (folder `Prequal`, 30s refresh interval). Datasources (Prometheus + Loki) come from `monitoring/grafana-datasources.yml`.

## Next Steps

1. **Distributed Tracing**: Implement OpenTelemetry
2. **APM**: Consider application performance monitoring
3. **Log retention tuning**: adjust Loki retention in `monitoring/local-config.yaml`

## Related Files

- `app/logging_config.py` - Logging configuration
- `app/middleware/correlation_id.py` - Correlation ID middleware
- `app/metrics.py` - Prometheus metrics instrumentation
- `api/health.py` - Health check endpoints
- `docker-compose.monitoring.yml` - Loki/Grafana/Prometheus/Promtail stack
- `monitoring/promtail-config.yml` - Log shipper configuration
- `monitoring/prometheus.yml` - Prometheus scrape configuration
- `monitoring/grafana-dashboards-provider.yml` - Dashboard provisioning provider
- `monitoring/grafana-datasources.yml` - Grafana datasources
- `monitoring/alerts.yml` - Prometheus alert rules
- `monitoring/ALERTING.md` - Alerting guide
- `docker-compose.staging.yml` - Staging environment
