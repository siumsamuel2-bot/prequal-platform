import { useState, useEffect } from 'react';
import { analyticsApi, PerformanceMetricsData } from '../api/client';
import { Loading } from './Loading';
import { useToast } from './ToastContext';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Legend
} from 'recharts';
import './Dashboard.css';

const PerformanceDashboard = () => {
  const toast = useToast();
  const [metrics, setMetrics] = useState<PerformanceMetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [historyData, setHistoryData] = useState<any[]>([]);

  useEffect(() => {
    const fetchPerformanceData = async () => {
      setLoading(true);
      try {
        const metricsData = await analyticsApi.getPerformanceMetrics();
        setMetrics(metricsData);

        const historyResponse = await fetch('/api/analytics/system-health?service_name=prequal-api', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const history = await historyResponse.json();
        setHistoryData(history.map((h: any) => ({
          time: new Date(h.computed_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
          avgValue: h.avg_value,
          p95Value: h.p95_value,
        })));
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to load performance metrics');
      } finally {
        setLoading(false);
      }
    };
    fetchPerformanceData();
  }, [toast]);

  if (loading) return <div className="dashboard"><Loading message="Loading performance metrics..." fullScreen /></div>;
  if (!metrics) return null;

  const responseTimeData = [
    { name: 'p50', value: metrics.p50_response_time_ms, color: '#10b981' },
    { name: 'p95', value: metrics.p95_response_time_ms, color: '#f59e0b' },
    { name: 'p99', value: metrics.p99_response_time_ms, color: '#ef4444' },
  ];

  const dbUtilizationPercent = metrics.max_db_connections > 0
    ? Math.round((metrics.active_db_connections / metrics.max_db_connections) * 100)
    : 0;

  const perfMetrics = [
    { label: 'Request Rate', value: `${metrics.requests_per_second.toFixed(2)} req/s`, icon: '📊', color: '#3b82f6' },
    { label: 'Error Rate', value: `${metrics.error_rate_percent.toFixed(2)}%`, icon: '⚠️', color: metrics.error_rate_percent > 5 ? '#ef4444' : '#10b981' },
    { label: 'Avg Response', value: `${metrics.avg_response_time_ms.toFixed(0)}ms`, icon: '⏱️', color: '#8b5cf6' },
    { label: 'p95 Response', value: `${metrics.p95_response_time_ms.toFixed(0)}ms`, icon: '🚀', color: '#f59e0b' },
    { label: 'Active DB Conn', value: `${metrics.active_db_connections}/${metrics.max_db_connections}`, icon: '🗄️', color: '#06b6d4' },
    { label: 'Active Requests', value: metrics.active_requests.toString(), icon: '🔄', color: '#10b981' },
  ];

  return (
    <div className="dashboard">
      <div className="dashboard-header" style={{ backgroundColor: '#6366f1' }}>
        <h1>Performance Monitoring</h1>
        <div className="dashboard-nav">
          <span>System Performance Dashboard</span>
        </div>
      </div>

      <div className="dashboard-content">
        <div className="metrics-grid">
          {perfMetrics.map((metric, index) => (
            <div key={index} className="metric-card" style={{ borderLeftColor: metric.color }}>
              <div className="metric-icon">{metric.icon}</div>
              <div className="metric-content">
                <div className="metric-value">{metric.value}</div>
                <div className="metric-label">{metric.label}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="dashboard-grid">
          <div className="dashboard-main">
            <div className="chart-section">
              <div className="section-header">
                <h2>Response Time Distribution</h2>
              </div>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={responseTimeData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis type="number" stroke="#6b7280" fontSize={12} unit="ms" />
                    <YAxis type="category" dataKey="name" stroke="#6b7280" fontSize={12} width={40} />
                    <Tooltip
                      contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                      formatter={(value: number) => [`${value.toFixed(2)}ms`, 'Latency']}
                    />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {responseTimeData.map((entry, index) => (
                        <rect key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="chart-section">
              <div className="section-header">
                <h2>System Health Over Time</h2>
              </div>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={historyData.length > 0 ? historyData : [{ time: 'Now', avgValue: 0, p95Value: 0 }]}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="time" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} />
                    <Tooltip
                      contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="avgValue" stroke="#3b82f6" strokeWidth={2} dot={false} name="Avg Value" />
                    <Line type="monotone" dataKey="p95Value" stroke="#ef4444" strokeWidth={2} dot={false} name="p95 Value" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="charts-row">
              <div className="chart-section half">
                <h2>Database Connection Pool</h2>
                <div className="quick-stats">
                  <div className="stat-row">
                    <span>Active Connections</span>
                    <span className="stat-value">{metrics.active_db_connections}</span>
                  </div>
                  <div className="stat-row">
                    <span>Max Connections</span>
                    <span className="stat-value">{metrics.max_db_connections}</span>
                  </div>
                  <div className="stat-row">
                    <span>Utilization</span>
                    <span className={`stat-value ${dbUtilizationPercent > 80 ? 'stat-danger' : dbUtilizationPercent > 60 ? 'stat-warning' : ''}`}>
                      {dbUtilizationPercent}%
                    </span>
                  </div>
                  <div className="stat-row">
                    <span>Rate Limit Hits</span>
                    <span className="stat-value">{metrics.rate_limit_hits}</span>
                  </div>
                </div>
              </div>

              <div className="chart-section half">
                <h2>Performance Summary</h2>
                <div className="quick-stats">
                  <div className="stat-row">
                    <span>Requests/sec</span>
                    <span className="stat-value">{metrics.requests_per_second.toFixed(2)}</span>
                  </div>
                  <div className="stat-row">
                    <span>Error Rate</span>
                    <span className={`stat-value ${metrics.error_rate_percent > 1 ? 'stat-danger' : ''}`}>
                      {metrics.error_rate_percent.toFixed(2)}%
                    </span>
                  </div>
                  <div className="stat-row">
                    <span>Active Requests</span>
                    <span className="stat-value">{metrics.active_requests}</span>
                  </div>
                  <div className="stat-row">
                    <span>Last Updated</span>
                    <span className="stat-value">{metrics.computed_at ? new Date(metrics.computed_at).toLocaleTimeString() : 'N/A'}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="dashboard-sidebar">
            <div className="chart-section">
              <h2>Response Time Percentiles</h2>
              <div className="quick-stats">
                <div className="stat-row">
                  <span>p50 (Median)</span>
                  <span className="stat-value" style={{ color: '#10b981' }}>{metrics.p50_response_time_ms.toFixed(0)}ms</span>
                </div>
                <div className="stat-row">
                  <span>p95</span>
                  <span className="stat-value" style={{ color: '#f59e0b' }}>{metrics.p95_response_time_ms.toFixed(0)}ms</span>
                </div>
                <div className="stat-row">
                  <span>p99</span>
                  <span className="stat-value" style={{ color: '#ef4444' }}>{metrics.p99_response_time_ms.toFixed(0)}ms</span>
                </div>
              </div>
            </div>

            <div className="chart-section">
              <h2>System Status</h2>
              <div className="quick-stats">
                <div className="stat-row">
                  <span>Database</span>
                  <span className="stat-value" style={{ color: dbUtilizationPercent < 80 ? '#10b981' : '#ef4444' }}>
                    {dbUtilizationPercent < 60 ? 'Healthy' : dbUtilizationPercent < 80 ? 'Moderate' : 'High'}
                  </span>
                </div>
                <div className="stat-row">
                  <span>API Health</span>
                  <span className="stat-value" style={{ color: metrics.error_rate_percent < 1 ? '#10b981' : metrics.error_rate_percent < 5 ? '#f59e0b' : '#ef4444' }}>
                    {metrics.error_rate_percent < 1 ? 'Healthy' : metrics.error_rate_percent < 5 ? 'Degraded' : 'Critical'}
                  </span>
                </div>
              </div>
            </div>

            <div className="quick-actions">
              <h2>Quick Actions</h2>
              <div className="action-buttons">
                <button className="action-btn" onClick={() => window.location.href = '/dashboard'}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                  </svg>
                  Back to Dashboard
                </button>
                <button className="action-btn" onClick={() => window.open('/metrics', '_blank')}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  View Prometheus Metrics
                </button>
                <button className="action-btn" onClick={() => window.open('http://localhost:3000', '_blank')}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  Open Grafana Dashboard
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PerformanceDashboard;