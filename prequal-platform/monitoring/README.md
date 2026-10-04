# Monitoring Configuration

Comprehensive production monitoring stack for the Prequal Platform using open-source tools.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Application│────▶│  Prometheus  │────▶│   Grafana   │
│   (FastAPI) │     │  (Metrics)   │     │ (Dashboards)│
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                    │
       ▼                    ▼                    │
┌─────────────┐     ┌──────────────┐            │
│   Promtail  │────▶│    Loki      │◀───────────┘
│  (Log Ship) │     │   (Logs)     │
└─────────────┘     └──────────────┘
```

## Components

| Component | Purpose | Port |
|-----------|---------|------|
| Prometheus | Metrics collection and alerting | 9090 |
| Grafana | Visualization and dashboards | 3000 |
| Loki | Lightweight log aggregation | 3100 |
| Promtail | Log shipper to Loki | - |
| Node Exporter | System metrics (CPU, memory, disk) | 9100 |
| cAdvisor | Container metrics | 8080 |

## Quick Start

### 1. Start the Monitoring Stack

```bash
# From the prequal-platform directory
docker-compose -f docker-compose.monitoring.yml up -d
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Status Page**: Open `monitoring/status-page.html` in a browser

### 3. Verify Metrics Endpoint

The application must expose `/metrics` for Prometheus scraping. Add to your FastAPI app:

```python
from app.metrics import setup_metrics

app = FastAPI()
setup_metrics(app)  # Adds /metrics endpoint
```

Install the required package:

```bash
pip install prometheus-client
```

## Files

| File | Purpose |
|------|---------|
| `docker-compose.monitoring.yml` | Full monitoring stack (Prometheus, Grafana, Loki) |
| `prometheus.yml` | Prometheus scrape configuration |
| `alerts.yml` | Alert rules with production thresholds |
| `grafana-dashboard.json` | Prebuilt Grafana dashboard with 14 panels |
| `grafana-datasources.yml` | Auto-configured datasources |
| `promtail-config.yml` | Log shipping configuration |
| `status-page.html` | Internal status page |
| `../scripts/weekly_health_report.py` | Automated weekly report generator |

## Metrics Exposed

The application exposes these Prometheus metrics (when instrumented):

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests (method, endpoint, status) |
| `http_request_duration_seconds` | Histogram | Request latency with buckets |
| `http_requests_in_progress` | Gauge | Current in-flight requests |
| `db_pool_active_connections` | Gauge | Active DB connections |
| `db_pool_max_connections` | Gauge | Maximum DB pool size |
| `up` | Gauge | Service availability (1=up, 0=down) |

System metrics from node-exporter and cAdvisor:
- CPU usage per core
- Memory usage and availability
- Disk space and I/O
- Network traffic
- Container resource usage

## Alert Thresholds

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| ServiceDown | Service unreachable 2+ min | Critical | Page on-call |
| HighErrorRate | 5xx errors > 5% for 5 min | High | Investigate logs |
| HighLatency | p95 latency > 500ms for 5 min | Medium | Review slow queries |
| DatabasePoolExhaustion | Pool > 80% full for 5 min | High | Scale or debug leaks |
| DiskSpaceLow | Disk usage > 80% for 10 min | Medium | Clean or expand |
| ContainerMemoryPressure | Container > 90% memory | High | Restart or scale |

## Grafana Dashboards

The prebuilt dashboard includes:

1. **Service Health Status** - Real-time UP/DOWN indicator
2. **Request Rate** - Current requests per second
3. **Error Rate** - 5xx error percentage
4. **Active DB Connections** - Connection pool usage
5. **API Response Times** - p50, p95, p99 latency trends
6. **Request Rate & Error Rate** - Combined view
7. **Database Connection Pool** - Historical pool usage
8. **User Activity** - Non-health endpoint requests
9. **System Resources - CPU** - User vs system CPU
10. **System Resources - Memory** - Used vs available
11. **Disk Usage** - Per-mountpoint utilization
12. **Container Memory Usage** - Per-container breakdown
13. **Alert Summary** - Active alerts list
14. **Recent Logs** - Live log tail from Loki

## Weekly Health Report

Automated weekly report generation:

```bash
# Generate HTML report
python scripts/weekly_health_report.py -o reports/weekly.html

# Generate text report
python scripts/weekly_health_report.py -f text -o reports/weekly.txt

# With custom URLs
python scripts/weekly_health_report.py \
  --prometheus-url http://prometheus:9090 \
  --grafana-url http://grafana:3000
```

### Automate Weekly Reports

Add to crontab (Linux) or Task Scheduler (Windows):

```bash
# Every Monday at 8 AM
0 8 * * 1 cd /path/to/prequal-platform && \
  python scripts/weekly_health_report.py \
  -o reports/weekly_$(date +\%Y\%m\%d).html
```

## Status Page

The internal status page (`status-page.html`) provides:
- Real-time service health indicators
- Key metrics (uptime, latency, error rate, request rate)
- Recent incidents list
- Links to Grafana and Prometheus

Deploy behind your reverse proxy or open directly in a browser.

## Production Deployment

### Docker Compose (Recommended)

```bash
# Production with monitoring
docker-compose -f docker-compose.production.yml \
  -f docker-compose.monitoring.yml \
  up -d
```

### Kubernetes

For Kubernetes deployments, use:
- Prometheus Operator for metrics
- Grafana helm chart for dashboards
- Loki stack for logging

### AWS Native

The `infrastructure/monitoring.tf` file provides CloudWatch alarms and dashboards for AWS deployments.

## Troubleshooting

### Prometheus not scraping metrics

1. Verify `/metrics` endpoint is accessible:
   ```bash
   curl http://backend:8000/metrics
   ```

2. Check Prometheus targets:
   - Open http://localhost:9090/targets
   - All targets should show "UP"

### Grafana shows no data

1. Verify Prometheus datasource is configured
2. Check time range selector (try last 1 hour)
3. Ensure metrics are being exposed by the application

### Logs not appearing in Grafana

1. Verify Promtail is running:
   ```bash
   docker logs prequal-promtail
   ```

2. Check log paths in `promtail-config.yml`
3. Ensure logs directory is mounted correctly

## Security Considerations

- Change default Grafana admin password in production
- Do not expose Prometheus or Grafana directly to the internet
- Use reverse proxy with authentication for external access
- Keep sensitive data (DB URLs, API keys) out of monitoring tools
- Enable TLS for Grafana in production

## Next Steps

1. ✅ Grafana dashboards configured
2. ✅ Alert thresholds defined
3. ✅ Log aggregation with Loki
4. ✅ Weekly health report automation
5. ✅ Status page for internal visibility
6. ✅ Add Prometheus metrics to FastAPI application (MID-134)
7. ⏳ Configure alerting channels (Slack, PagerDuty, email)
8. ⏳ Create runbooks for each alert type

## What Was Implemented (MID-134)

### Application Metrics Integration
- `api/main.py` calls `setup_metrics(app)` on startup → `/metrics` endpoint exposed
- Database connection pool metrics collected every 15s via background task (`_update_db_pool_metrics_loop`)
- Metrics: `http_requests_total`, `http_request_duration_seconds`, `http_requests_in_progress`, `db_pool_active_connections`, `db_pool_max_connections`, `rate_limit_hits_total`

### SLO Burn Rate Alerts (Prometheus + Grafana)
Multi-window, multi-burn-rate alerts for modern SLO-based alerting:
- `PrequalAvailabilityBudgetBurningFast` — 14.4x burn rate, 4min, critical
- `PrequalAvailabilityBudgetBurning` — 6x burn rate, 15min, warning
- `PrequalLatencySLECBudgetBurningFast` — latency SLO critical, 4min
- `PrequalHighLatencyWarning` — p95 > 1s, 10min, warning
- `HighClientErrorRate` — 4xx > 10%, 10min, warning

### Grafana Dashboard v3
- **Availability SLO — Error Budget Remaining** (gauge, % of 30-day budget remaining)
- **Error Budget Burn Rate (30d)** (stat, burn rate vs sustainable 1x)
- SLO threshold line (500ms) added to API Response Times panel
- Latency panel: p50, p95, p99 with threshold markers

### SLO Documentation
- `monitoring/slo_targets.md` — SLO definitions, error budget math, burn rate guide
