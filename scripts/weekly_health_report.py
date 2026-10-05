#!/usr/bin/env python3
"""
Weekly Health Report Generator for Prequal Platform

Generates automated health reports from Prometheus metrics and Grafana dashboards.
Supports HTML and text output formats.

Usage:
    python weekly_health_report.py -o reports/weekly.html
    python weekly_health_report.py -f text -o reports/weekly.txt
    python weekly_health_report.py --prometheus-url http://prometheus:9090 --grafana-url http://grafana:3000
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import requests

PROMETHEUS_URL = "http://localhost:9090"
GRAFANA_URL = "http://localhost:3000"
GRAFANA_API_KEY = "admin:admin"


@dataclass
class HealthReport:
    timestamp: str
    service_status: str
    uptime_percentage: float
    total_requests: int
    error_rate: float
    p95_latency_ms: float
    p99_latency_ms: float
    db_pool_usage_percent: float
    active_alerts: int
    burn_rate: float
    error_budget_remaining: float


def query_prometheus(query: str, timeout: int = 30) -> Optional[dict]:
    """Query Prometheus API and return JSON result."""
    url = f"{PROMETHEUS_URL}/api/v1/query"
    try:
        response = requests.get(url, params={"query": query}, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success" and data.get("data", {}).get("result"):
            return data["data"]["result"]
        return None
    except requests.RequestException as e:
        print(f"Prometheus query failed: {e}", file=sys.stderr)
        return None


def get_metric_value(result: list, default: float = 0.0) -> float:
    """Extract scalar value from Prometheus query result."""
    if result and len(result) > 0:
        try:
            return float(result[0]["value"][1])
        except (IndexError, ValueError):
            pass
    return default


def calculate_uptime() -> tuple[str, float]:
    """Calculate service uptime over the past 30 days."""
    query = 'sum(rate(http_requests_total[30d])) / sum(rate(http_requests_total[30d])) * 100'
    result = query_prometheus(query)
    if result is None:
        return "UNKNOWN", 0.0
    uptime = get_metric_value(result, 100.0)
    status = "HEALTHY" if uptime >= 99.9 else "DEGRADED" if uptime >= 99.0 else "CRITICAL"
    return status, uptime


def get_request_stats() -> tuple[int, float]:
    """Get total requests and error rate over the past 24 hours."""
    total_query = 'sum(increase(http_requests_total[24h]))'
    error_query = 'sum(increase(http_requests_total{status=~"5.."}[24h]))'

    total_result = query_prometheus(total_query)
    error_result = query_prometheus(error_query)

    total_requests = int(get_metric_value(total_result, 0))
    errors = get_metric_value(error_result, 0)
    error_rate = (errors / total_requests * 100) if total_requests > 0 else 0.0

    return total_requests, error_rate


def get_latency_stats() -> tuple[float, float]:
    """Get p95 and p99 latency in milliseconds."""
    p95_query = 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000'
    p99_query = 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000'

    p95_result = query_prometheus(p95_query)
    p99_result = query_prometheus(p99_query)

    p95 = get_metric_value(p95_result, 0)
    p99 = get_metric_value(p99_result, 0)

    return p95, p99


def get_db_pool_usage() -> float:
    """Get database connection pool usage percentage."""
    active_query = 'db_pool_active_connections'
    max_query = 'db_pool_max_connections'

    active_result = query_prometheus(active_query)
    max_result = query_prometheus(max_query)

    active = get_metric_value(active_result, 0)
    maximum = get_metric_value(max_result, 1)

    if maximum > 0:
        return (active / maximum) * 100
    return 0.0


def get_burn_rate() -> float:
    """Calculate error budget burn rate over the past hour."""
    query = '(sum(rate(http_requests_total{status=~"5.."}[1h])) / sum(rate(http_requests_total[1h]))) / 0.001'
    result = query_prometheus(query)
    return get_metric_value(result, 1.0)


def get_error_budget_remaining() -> float:
    """Calculate remaining error budget percentage."""
    query = '100 * (1 - (sum(rate(http_requests_total{status=~"5.."}[30d])) / sum(rate(http_requests_total[30d])))) / 0.999'
    result = query_prometheus(query)
    return max(0, min(100, get_metric_value(result, 100.0)))


def get_active_alerts() -> int:
    """Get count of currently firing alerts from Prometheus."""
    query = 'count(ALERTS{alertstate="firing"})'
    result = query_prometheus(query)
    return int(get_metric_value(result, 0))


def collect_health_data() -> HealthReport:
    """Collect all health metrics and return a HealthReport."""
    status, uptime = calculate_uptime()
    total_requests, error_rate = get_request_stats()
    p95, p99 = get_latency_stats()
    db_pool = get_db_pool_usage()
    burn_rate = get_burn_rate()
    error_budget = get_error_budget_remaining()
    active_alerts = get_active_alerts()

    return HealthReport(
        timestamp=datetime.utcnow().isoformat() + "Z",
        service_status=status,
        uptime_percentage=uptime,
        total_requests=total_requests,
        error_rate=error_rate,
        p95_latency_ms=p95,
        p99_latency_ms=p99,
        db_pool_usage_percent=db_pool,
        active_alerts=active_alerts,
        burn_rate=burn_rate,
        error_budget_remaining=error_budget,
    )


def generate_html_report(report: HealthReport) -> str:
    """Generate HTML report from health data."""
    status_color = {
        "HEALTHY": "#28a745",
        "DEGRADED": "#ffc107",
        "CRITICAL": "#dc3545",
        "UNKNOWN": "#6c757d",
    }.get(report.service_status, "#6c757d")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prequal Platform - Weekly Health Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .header .timestamp {{
            opacity: 0.8;
            font-size: 0.9em;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card h3 {{
            margin: 0 0 15px 0;
            color: #555;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 0;
        }}
        .metric.small {{
            font-size: 1.8em;
        }}
        .metric.error {{
            color: #dc3545;
        }}
        .metric.warning {{
            color: #ffc107;
        }}
        .metric.success {{
            color: #28a745;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            color: white;
            font-weight: bold;
            font-size: 1.2em;
        }}
        .alert-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .alert-list li {{
            padding: 10px;
            margin-bottom: 8px;
            background: #f8f9fa;
            border-left: 4px solid #dc3545;
            border-radius: 4px;
        }}
        .alert-list li.warning {{
            border-left-color: #ffc107;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }}
        .links a {{
            color: #667eea;
            text-decoration: none;
            margin: 0 10px;
        }}
        .links a:hover {{
            text-decoration: underline;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .trend {{
            font-size: 0.8em;
            margin-left: 8px;
        }}
        .trend.up {{ color: #28a745; }}
        .trend.down {{ color: #dc3545; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Prequal Platform - Weekly Health Report</h1>
        <div class="timestamp">Generated: {report.timestamp}</div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Service Status</h3>
            <span class="status-badge" style="background: {status_color}">{report.service_status}</span>
        </div>
        <div class="card">
            <h3>Uptime (30d)</h3>
            <p class="metric {'success' if report.uptime_percentage >= 99.9 else 'warning' if report.uptime_percentage >= 99 else 'error'}">{report.uptime_percentage:.3f}%</p>
        </div>
        <div class="card">
            <h3>Total Requests (24h)</h3>
            <p class="metric small">{report.total_requests:,}</p>
        </div>
        <div class="card">
            <h3>Error Rate (5xx)</h3>
            <p class="metric small {'error' if report.error_rate > 1 else 'success'}">{report.error_rate:.2f}%</p>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Latency - p95</h3>
            <p class="metric small {'error' if report.p95_latency_ms > 500 else 'warning' if report.p95_latency_ms > 250 else 'success'}">{report.p95_latency_ms:.1f} ms</p>
        </div>
        <div class="card">
            <h3>Latency - p99</h3>
            <p class="metric small {'error' if report.p99_latency_ms > 1000 else 'warning' if report.p99_latency_ms > 500 else 'success'}">{report.p99_latency_ms:.1f} ms</p>
        </div>
        <div class="card">
            <h3>DB Pool Usage</h3>
            <p class="metric small {'error' if report.db_pool_usage_percent > 80 else 'warning' if report.db_pool_usage_percent > 60 else 'success'}">{report.db_pool_usage_percent:.1f}%</p>
        </div>
        <div class="card">
            <h3>Error Budget Burn Rate</h3>
            <p class="metric small {'error' if report.burn_rate > 14.4 else 'warning' if report.burn_rate > 6 else 'success'}">{report.burn_rate:.1f}x</p>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Error Budget Remaining</h3>
            <p class="metric small {'error' if report.error_budget_remaining < 50 else 'warning' if report.error_budget_remaining < 75 else 'success'}">{report.error_budget_remaining:.1f}%</p>
        </div>
        <div class="card">
            <h3>Active Alerts</h3>
            <p class="metric small {'error' if report.active_alerts > 0 else 'success'}">{report.active_alerts}</p>
        </div>
    </div>

    <div class="card">
        <h3>Active Alerts</h3>
        {"<ul class=\"alert-list\"><li>No active alerts</li></ul>" if report.active_alerts == 0 else f"<ul class=\"alert-list\"><li>{report.active_alerts} alert(s) firing - see Grafana for details</li></ul>"}
    </div>

    <div class="footer">
        <div class="links">
            <a href="{GRAFANA_URL}" target="_blank">Grafana Dashboard</a>
            <a href="{PROMETHEUS_URL}" target="_blank">Prometheus</a>
        </div>
        <p>Prequal Platform Monitoring | SLO Target: 99.9% Availability | Latency: p95 < 500ms</p>
    </div>
</body>
</html>"""


def generate_text_report(report: HealthReport) -> str:
    """Generate plain text report from health data."""
    lines = [
        "=" * 60,
        "PREQUAL PLATFORM - WEEKLY HEALTH REPORT",
        "=" * 60,
        f"Generated: {report.timestamp}",
        "",
        "SERVICE STATUS",
        "-" * 40,
        f"  Overall Status: {report.service_status}",
        f"  Uptime (30d):  {report.uptime_percentage:.3f}%",
        "",
        "REQUEST METRICS (24h)",
        "-" * 40,
        f"  Total Requests: {report.total_requests:,}",
        f"  Error Rate:     {report.error_rate:.2f}%",
        "",
        "LATENCY METRICS",
        "-" * 40,
        f"  p95 Latency: {report.p95_latency_ms:.1f} ms",
        f"  p99 Latency: {report.p99_latency_ms:.1f} ms",
        "",
        "DATABASE",
        "-" * 40,
        f"  Pool Usage: {report.db_pool_usage_percent:.1f}%",
        "",
        "SLO METRICS",
        "-" * 40,
        f"  Error Budget Burn Rate:    {report.burn_rate:.1f}x",
        f"  Error Budget Remaining:   {report.error_budget_remaining:.1f}%",
        f"  Active Alerts:            {report.active_alerts}",
        "",
        "LINKS",
        "-" * 40,
        f"  Grafana:   {GRAFANA_URL}",
        f"  Prometheus: {PROMETHEUS_URL}",
        "",
        "SLO Targets: 99.9% Availability | p95 Latency < 500ms",
        "=" * 60,
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly health reports for Prequal Platform"
    )
    parser.add_argument(
        "-o", "--output",
        default="weekly_health_report.html",
        help="Output file path (default: weekly_health_report.html)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["html", "text"],
        default="html",
        help="Output format (default: html)"
    )
    parser.add_argument(
        "--prometheus-url",
        default=PROMETHEUS_URL,
        help=f"Prometheus URL (default: {PROMETHEUS_URL})"
    )
    parser.add_argument(
        "--grafana-url",
        default=GRAFANA_URL,
        help=f"Grafana URL (default: {GRAFANA_URL})"
    )

    args = parser.parse_args()

    global PROMETHEUS_URL, GRAFANA_URL
    PROMETHEUS_URL = args.prometheus_url.rstrip("/")
    GRAFANA_URL = args.grafana_url.rstrip("/")

    print("Collecting health metrics from Prometheus...")
    report = collect_health_data()

    print(f"Generating {args.format} report...")
    if args.format == "html":
        content = generate_html_report(report)
    else:
        content = generate_text_report(report)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Report saved to: {args.output}")
    print(f"\nSummary:")
    print(f"  Status: {report.service_status}")
    print(f"  Uptime: {report.uptime_percentage:.3f}%")
    print(f"  Error Rate: {report.error_rate:.2f}%")
    print(f"  Active Alerts: {report.active_alerts}")


if __name__ == "__main__":
    main()