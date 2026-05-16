# Prequal Platform - Monitoring & Logging Guide

## Overview

This guide covers the monitoring and logging setup for the Prequal compliance platform.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Application    │────▶│  Structured Logs │────▶│  Log Aggregator │
│  (FastAPI)      │     │  (JSON)          │     │  (ELK/Loki)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │
        ▼                        ▼
┌─────────────────┐     ┌──────────────────┐
│  Health Checks  │     │  Metrics         │
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

## Log Aggregation (Optional)

### Development - Console Logs

For local development, logs output to console:

```bash
docker-compose -f docker-compose.staging.yml logs -f backend
```

### Production - ELK Stack

For production, use the optional ELK stack:

```bash
# Start logging infrastructure
docker-compose -f docker-compose.logging.yml up -d

# Access Kibana
open http://localhost:5601
```

### Configuration

1. **Elasticsearch**: Log storage and search (port 9200)
2. **Logstash**: Log processing pipeline (port 5044)
3. **Kibana**: Visualization and dashboards (port 5601)
4. **Filebeat**: Log shipper (sends logs to Logstash)

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

## Next Steps

1. **Metrics Collection**: Add Prometheus metrics
2. **Distributed Tracing**: Implement OpenTelemetry
3. **Alerting**: Configure PagerDuty/Slack alerts
4. **Dashboards**: Create Grafana dashboards
5. **APM**: Consider application performance monitoring

## Related Files

- `app/logging_config.py` - Logging configuration
- `api/health.py` - Health check endpoints
- `docker-compose.logging.yml` - ELK stack setup
- `docker-compose.staging.yml` - Staging environment
