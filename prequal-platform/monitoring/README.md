# Monitoring Configuration

This directory contains monitoring and alerting configurations for the Prequal Platform.

## Files

| File | Purpose |
|------|---------|
| `prometheus.yml` | Prometheus scrape configuration |
| `alerts.yml` | Alert rules for Prometheus Alertmanager |
| `grafana-dashboard.json` | Prebuilt Grafana dashboard |

## Setup

### Prometheus

```bash
# Copy configuration
cp monitoring/prometheus.yml /etc/prometheus/prometheus.yml

# Start Prometheus
prometheus --config.file=/etc/prometheus/prometheus.yml
```

### Grafana

1. Access Grafana at http://localhost:3000 (default credentials: admin/admin)
2. Add Prometheus data source (http://prometheus:9090)
3. Import dashboard from `grafana-dashboard.json`

### Alertmanager

Configure alert routing in Alertmanager for notification delivery.

## Metrics

The application exposes the following metrics (when instrumented):

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency histogram
- `db_pool_active_connections` - Active database connections
- `db_pool_max_connections` - Maximum pool size
- `up` - Service availability

## Alerts

| Alert | Severity | Description |
|-------|----------|-------------|
| ServiceDown | Critical | Service unreachable for 2+ minutes |
| HighErrorRate | High | Error rate > 5% for 5+ minutes |
| HighLatency | Medium | p95 latency > 2s for 10+ minutes |
| DatabasePoolExhaustion | High | DB pool > 80% full |
| DiskSpaceLow | Medium | Disk usage > 80% |

## Next Steps

1. Add Prometheus metrics client to FastAPI application
2. Configure alerting channels (Slack, PagerDuty, email)
3. Create additional dashboards for business metrics
4. Set up log-to-metric conversion for custom alerts
