#!/usr/bin/env python3
"""
Weekly Health Report Generator for Prequal Platform

Generates a comprehensive weekly health report including:
- Uptime statistics
- Error rate trends
- Performance metrics (p95 latency)
- Database connection pool usage
- Alert summary
- Resource utilization

Usage:
    python scripts/weekly_health_report.py --output report.html

Requirements:
    - prometheus_client
    - requests
    - jinja2 (for HTML templating)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any

try:
    import requests
    from jinja2 import Template
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install requests jinja2")
    sys.exit(1)


PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
OUTPUT_DIR = os.getenv("REPORT_OUTPUT_DIR", "./reports")


def query_prometheus(query: str, range: str = "7d", step: str = "1h") -> Dict:
    """Query Prometheus for metrics data."""
    url = f"{PROMETHEUS_URL}/api/v1/query_range"
    params = {
        "query": query,
        "start": datetime.utcnow() - timedelta(days=7),
        "end": datetime.utcnow(),
        "step": step
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error querying Prometheus: {e}")
        return {"status": "error", "data": {"result": []}}


def get_uptime_stats() -> Dict[str, Any]:
    """Calculate uptime statistics for the week."""
    query = 'avg_over_time(up{job="prequal-backend"}[7d])'
    result = query_prometheus(query)
    
    if result.get("status") == "success" and result["data"]["result"]:
        uptime_percent = float(result["data"]["result"][0]["values"][-1][1]) * 100
        return {
            "uptime_percent": round(uptime_percent, 2),
            "downtime_minutes": round((100 - uptime_percent) * 7 * 24 * 60 / 100, 1)
        }
    return {"uptime_percent": "N/A", "downtime_minutes": "N/A"}


def get_error_rate_stats() -> Dict[str, Any]:
    """Get error rate statistics."""
    query = 'rate(http_requests_total{status=~"5.."}[1h]) / rate(http_requests_total[1h]) * 100'
    result = query_prometheus(query)
    
    if result.get("status") == "success" and result["data"]["result"]:
        values = [float(v[1]) for v in result["data"]["result"][0]["values"]]
        return {
            "avg_error_rate": round(sum(values) / len(values), 2) if values else 0,
            "max_error_rate": round(max(values), 2) if values else 0,
            "total_5xx_errors": "Check Prometheus for exact count"
        }
    return {"avg_error_rate": "N/A", "max_error_rate": "N/A"}


def get_latency_stats() -> Dict[str, Any]:
    """Get latency percentiles."""
    query_p95 = 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[7d]))'
    query_p99 = 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[7d]))'
    
    result_p95 = query_prometheus(query_p95)
    result_p99 = query_prometheus(query_p99)
    
    stats = {}
    
    if result_p95.get("status") == "success" and result_p95["data"]["result"]:
        values = [float(v[1]) * 1000 for v in result_p95["data"]["result"][0]["values"]]
        stats["p95_avg_ms"] = round(sum(values) / len(values), 1) if values else 0
        stats["p95_max_ms"] = round(max(values), 1) if values else 0
    
    if result_p99.get("status") == "success" and result_p99["data"]["result"]:
        values = [float(v[1]) * 1000 for v in result_p99["data"]["result"][0]["values"]]
        stats["p99_avg_ms"] = round(sum(values) / len(values), 1) if values else 0
        stats["p99_max_ms"] = round(max(values), 1) if values else 0
    
    return stats or {"p95_avg_ms": "N/A", "p99_avg_ms": "N/A"}


def get_db_pool_stats() -> Dict[str, Any]:
    """Get database connection pool statistics."""
    query = 'avg_over_time(db_pool_active_connections[7d])'
    result = query_prometheus(query)
    
    if result.get("status") == "success" and result["data"]["result"]:
        values = [float(v[1]) for v in result["data"]["result"][0]["values"]]
        return {
            "avg_connections": round(sum(values) / len(values), 1) if values else 0,
            "max_connections": round(max(values), 1) if values else 0
        }
    return {"avg_connections": "N/A", "max_connections": "N/A"}


def get_request_volume() -> Dict[str, Any]:
    """Get total request volume for the week."""
    query = 'sum(increase(http_requests_total[7d]))'
    result = query_prometheus(query)
    
    if result.get("status") == "success" and result["data"]["result"]:
        total = int(float(result["data"]["result"][0]["values"][-1][1]))
        return {"total_requests": f"{total:,}"}
    return {"total_requests": "N/A"}


def get_alert_summary() -> List[Dict]:
    """Get summary of triggered alerts (would need Alertmanager integration)."""
    # This is a placeholder - in production, query Alertmanager API
    return [
        {"alert": "ServiceDown", "count": 0, "last_triggered": "Never"},
        {"alert": "HighErrorRate", "count": 0, "last_triggered": "Never"},
        {"alert": "HighLatency", "count": 0, "last_triggered": "Never"},
    ]


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Prequal Platform - Weekly Health Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .metric-card { background: #f8f9fa; padding: 20px; border-radius: 6px; border-left: 4px solid #007bff; }
        .metric-value { font-size: 2em; font-weight: bold; color: #007bff; }
        .metric-label { color: #666; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: 600; }
        .status-good { color: #28a745; }
        .status-warning { color: #ffc107; }
        .status-critical { color: #dc3545; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 0.9em; }
        .links { margin-top: 20px; }
        .links a { color: #007bff; text-decoration: none; margin-right: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Prequal Platform - Weekly Health Report</h1>
        <p><strong>Report Period:</strong> {{ report_date }} (Last 7 days)</p>
        <p><strong>Generated:</strong> {{ generated_at }}</p>
        
        <h2>Executive Summary</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value {% if uptime.uptime_percent == 'N/A' or uptime.uptime_percent >= 99 %}status-good{% elif uptime.uptime_percent >= 95 %}status-warning{% else %}status-critical{% endif %}">{{ uptime.uptime_percent }}%</div>
                <div class="metric-label">Uptime</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ request_volume.total_requests }}</div>
                <div class="metric-label">Total Requests</div>
            </div>
            <div class="metric-card">
                <div class="metric-value {% if error_rate.avg_error_rate == 'N/A' or error_rate.avg_error_rate < 1 %}status-good{% elif error_rate.avg_error_rate < 5 %}status-warning{% else %}status-critical{% endif %}">{{ error_rate.avg_error_rate }}%</div>
                <div class="metric-label">Avg Error Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value {% if latency.p95_avg_ms == 'N/A' or latency.p95_avg_ms < 500 %}status-good{% elif latency.p95_avg_ms < 1000 %}status-warning{% else %}status-critical{% endif %}">{{ latency.p95_avg_ms }}ms</div>
                <div class="metric-label">Avg P95 Latency</div>
            </div>
        </div>
        
        <h2>Performance Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Average</th>
                <th>Maximum</th>
                <th>Threshold</th>
            </tr>
            <tr>
                <td>P95 Latency</td>
                <td>{{ latency.p95_avg_ms }}ms</td>
                <td>{{ latency.p95_max_ms }}ms</td>
                <td>500ms</td>
            </tr>
            <tr>
                <td>P99 Latency</td>
                <td>{{ latency.p99_avg_ms }}ms</td>
                <td>{{ latency.p99_max_ms }}ms</td>
                <td>1000ms</td>
            </tr>
            <tr>
                <td>Error Rate (5xx)</td>
                <td>{{ error_rate.avg_error_rate }}%</td>
                <td>{{ error_rate.max_error_rate }}%</td>
                <td>5%</td>
            </tr>
        </table>
        
        <h2>Database Connection Pool</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Average Active Connections</td>
                <td>{{ db_pool.avg_connections }}</td>
            </tr>
            <tr>
                <td>Maximum Active Connections</td>
                <td>{{ db_pool.max_connections }}</td>
            </tr>
        </table>
        
        <h2>Alert Summary</h2>
        <table>
            <tr>
                <th>Alert Name</th>
                <th>Times Triggered</th>
                <th>Last Triggered</th>
            </tr>
            {% for alert in alerts %}
            <tr>
                <td>{{ alert.alert }}</td>
                <td>{{ alert.count }}</td>
                <td>{{ alert.last_triggered }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <h2>Quick Links</h2>
        <div class="links">
            <a href="{{ grafana_url }}" target="_blank">📈 Grafana Dashboards</a>
            <a href="{{ prometheus_url }}" target="_blank">🔍 Prometheus</a>
            <a href="{{ grafana_url }}/alerting/list" target="_blank">🔔 Alert Rules</a>
        </div>
        
        <div class="footer">
            <p>This report is automatically generated weekly. For questions or issues, contact the DevOps team.</p>
            <p>Prequal Platform v1.0.0 | Monitoring Stack: Prometheus + Grafana + Loki</p>
        </div>
    </div>
</body>
</html>
"""


def generate_report(output_format: str = "html") -> str:
    """Generate the weekly health report."""
    
    # Collect all metrics
    uptime = get_uptime_stats()
    error_rate = get_error_rate_stats()
    latency = get_latency_stats()
    db_pool = get_db_pool_stats()
    request_volume = get_request_volume()
    alerts = get_alert_summary()
    
    report_data = {
        "report_date": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "uptime": uptime,
        "error_rate": error_rate,
        "latency": latency,
        "db_pool": db_pool,
        "request_volume": request_volume,
        "alerts": alerts,
        "prometheus_url": PROMETHEUS_URL,
        "grafana_url": GRAFANA_URL
    }
    
    if output_format == "html":
        template = Template(HTML_TEMPLATE)
        return template.render(**report_data)
    else:
        # Simple text format
        return f"""
Prequal Platform - Weekly Health Report
Generated: {report_data['generated_at']}

EXECUTIVE SUMMARY
-----------------
Uptime: {uptime['uptime_percent']}%
Total Requests: {request_volume['total_requests']}
Average Error Rate: {error_rate['avg_error_rate']}%
Average P95 Latency: {latency.get('p95_avg_ms', 'N/A')}ms

PERFORMANCE METRICS
-------------------
P95 Latency - Avg: {latency.get('p95_avg_ms', 'N/A')}ms | Max: {latency.get('p95_max_ms', 'N/A')}ms
P99 Latency - Avg: {latency.get('p99_avg_ms', 'N/A')}ms | Max: {latency.get('p99_max_ms', 'N/A')}ms
Error Rate - Avg: {error_rate['avg_error_rate']}% | Max: {error_rate['max_error_rate']}%

DATABASE CONNECTION POOL
------------------------
Average Active Connections: {db_pool['avg_connections']}
Maximum Active Connections: {db_pool['max_connections']}

ALERT SUMMARY
-------------
""" + "\\n".join([f"  - {a['alert']}: {a['count']} times" for a in alerts])


def main():
    parser = argparse.ArgumentParser(description="Generate weekly health report")
    parser.add_argument("--output", "-o", default="weekly_health_report.html",
                        help="Output file path")
    parser.add_argument("--format", "-f", choices=["html", "text"], default="html",
                        help="Output format")
    parser.add_argument("--prometheus-url", help="Prometheus URL (overrides env var)")
    parser.add_argument("--grafana-url", help="Grafana URL (overrides env var)")
    
    args = parser.parse_args()
    
    if args.prometheus_url:
        global PROMETHEUS_URL
        PROMETHEUS_URL = args.prometheus_url
    if args.grafana_url:
        global GRAFANA_URL
        GRAFANA_URL = args.grafana_url
    
    # Generate report
    report_content = generate_report(args.format)
    
    # Write to file
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report_content)
    
    print(f"Weekly health report generated: {args.output}")


if __name__ == "__main__":
    main()