# Prequal Platform — SLO Definitions & Targets

## SLO Overview

| SLO | Target | Window | Error Budget | Alert Thresholds |
|-----|--------|--------|-------------|-------------------|
| **Availability** | 99.9% | 30 days | 43.8 min/month | Burn at 6x → warning; burn at 14.4x → critical |
| **Latency (p95)** | < 500ms | 5 min | — | p95 > 500ms for 5min → high; > 1s for 10min → warning |
| **Latency (p99)** | < 1s | 5 min | — | p99 > 1s for 5min → warning |
| **Error Rate (5xx)** | < 1% | 5 min | — | > 5% for 5min → high; burn rate alerts for sustained |
| **Error Rate (4xx)** | < 10% | 5 min | — | > 10% for 10min → warning |
| **Database Availability** | 99.5% | 30 days | 3.65 hrs/month | Connection pool > 80% → high |

## Error Budget Mathematics

### Availability SLO (99.9%)
- Total minutes in 30 days: 43,200
- Error budget: 0.1% × 43,200 = **43.8 minutes**
- Sustainable error rate: 0.1% over 30 days

### Burn Rate Alerts

Burn rate = how many times faster than sustainable the error budget is consumed.

| Burn Rate | 1h Window | 5m Window | Time to Exhaust 30d Budget | Severity |
|-----------|-----------|-----------|----------------------------|----------|
| 1x (sustainable) | 0.0069% | — | 30 days | — |
| 6x | 0.0417% | 0.0417% | ~5 days | warning |
| 14.4x | 0.1% | 0.1% | ~2 days | critical |

### Latency SLO
- Target: 99% of requests have p95 latency ≤ 500ms
- Warning threshold: p95 > 1s for 10 minutes
- Critical: Less than 99% of requests within 500ms

## Alerting Schedule

| Severity | Response Time | Notification |
|----------|--------------|--------------|
| Critical (SLO burning fast) | < 5 minutes | SMS + Email + Slack |
| High (SLO at risk) | < 15 minutes | Email + Slack |
| Warning (degraded) | < 1 hour | Slack |
| Info (trend) | Next business day | Dashboard only |

## Dashboard Panels

The Grafana dashboard (`monitoring/grafana-dashboard.json`) includes:

1. **SLO Summary** — Current error budget remaining for availability
2. **Service Health Status** — Real-time UP/DOWN
3. **Request Rate** — req/s
4. **Error Rate (5xx)** — Error percentage with threshold markers
5. **Latency Distribution** — p50, p95, p99 with SLO threshold line
6. **Database Connection Pool** — Active vs max with exhaustion threshold
7. **Alert Summary** — All Firing/Resolved alerts

## Prometheus Alert Rules

SLO burn rate alerts are defined in `monitoring/alerts.yml` (Prometheus) and `monitoring/grafana-alerts.yml` (Grafana managed):

- `PrequalAvailabilityBudgetBurningFast` — Critical burn rate
- `PrequalAvailabilityBudgetBurning` — Warning burn rate
- `PrequalLatencySLECBudgetBurningFast` — Latency SLO critical
- `PrequalHighLatencyWarning` — p95 > 1s warning
- `HighClientErrorRate` — 4xx error rate warning

## Review Cadence

- **Weekly**: Review error budget consumption rate
- **Monthly**: SLO retrospective, adjust targets if needed
- **Quarterly**: Validate SLO alignment with business impact

## Runbooks

See `docs/INCIDENT_RESPONSE_PLAN.md` for alert-specific runbooks.

---

**Document version**: 1.0  
**Last updated**: 2026-06-15  
**Owner**: Senior Engineer (Platform)