import { useState, useEffect, useMemo } from 'react';
import { dashboardApi, complianceApi, DashboardSummary, ComplianceAlert } from '../api/client';
import { Loading, EmptyState } from './Loading';
import { useToast } from './ToastContext';
import { OnboardingChecklist } from './OnboardingChecklist';
import { useAnalytics } from '../hooks/useAnalytics';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';
import './Dashboard.css';

const COLORS = ['#10b981', '#f59e0b', '#ef4444', '#3b82f6'];

interface TrendData {
  date: string;
  compliance: number;
  violations: number;
  expiring: number;
}

interface DetailTabData {
  date: string;
  compliance: number;
  violations: number;
  expiring: number;
}

const TREND_PAGE_SIZE = 7;

const Dashboard = () => {
  const toast = useToast();
  const { trackExport } = useAnalytics();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [alerts, setAlerts] = useState<ComplianceAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [trendData, setTrendData] = useState<TrendData[]>([]);
  const [exportRange, setExportRange] = useState<'30' | '60' | '90'>('30');
  
  // Pagination state for trend chart
  const [trendPage, setTrendPage] = useState(0);
  
  // Detail tab state
  const [selectedPoint, setSelectedPoint] = useState<DetailTabData | null>(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      try {
        const [summaryData, alertsData, trendsData] = await Promise.all([
          dashboardApi.getSummary(),
          complianceApi.getAlerts(),
          fetch(`/api/analytics/compliance/trends?days=${exportRange}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
          }).then(res => res.json())
        ]);
        setSummary(summaryData);
        setAlerts(alertsData);
        const mapped = trendsData.map((t: any) => ({
          date: new Date(t.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
          compliance: t.compliance_percentage,
          violations: t.open_violations,
          expiring: t.expired_certifications
        }));
        setTrendData(mapped);
        // Reset pagination when data changes
        setTrendPage(0);
        setSelectedPoint(null);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, [exportRange, toast]);

  // Paginate trend data
  const pagedTrendData = useMemo(() => {
    const start = trendPage * TREND_PAGE_SIZE;
    return trendData.slice(start, start + TREND_PAGE_SIZE);
  }, [trendData, trendPage]);

  const totalTrendPages = Math.ceil(trendData.length / TREND_PAGE_SIZE);
  const canPrevTrend = trendPage > 0;
  const canNextTrend = trendPage < totalTrendPages - 1;

  const handlePrevTrend = () => {
    if (canPrevTrend) {
      setTrendPage(prev => prev - 1);
      setSelectedPoint(null);
    }
  };

  const handleNextTrend = () => {
    if (canNextTrend) {
      setTrendPage(prev => prev + 1);
      setSelectedPoint(null);
    }
  };

  const handleChartClick = (e: any) => {
    if (e && e.activePayload && e.activePayload[0]) {
      const data = e.activePayload[0].payload;
      setSelectedPoint(data);
    }
  };

  const handleExportCSV = async () => {
    trackExport('dashboard', 'csv');
    try {
      const response = await fetch(`/api/analytics/compliance/export?format=csv&expiration_bucket=${exportRange}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compliance-report-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('Report downloaded successfully');
    } catch (err) {
      toast.error('Failed to export report');
    }
  };

  const handleAlertClick = (alert: ComplianceAlert) => {
    if (alert.subcontractor_id) {
      window.location.href = `/subcontractors/${alert.subcontractor_id}`;
    }
  };

  if (loading) return <div className="dashboard"><Loading message="Loading dashboard..." fullScreen /></div>;
  if (!summary) return null;

  const metrics = [
    { label: 'Total Subcontractors', value: summary.total_subcontractors, icon: '🏢', color: '#3b82f6' },
    { label: 'Active Subcontractors', value: summary.active_subcontractors, icon: '✅', color: '#10b981' },
    { label: 'Compliance Rate', value: `${summary.compliance_rate}%`, icon: '📊', color: '#8b5cf6' },
    { label: 'Expiring This Month', value: summary.expiring_this_month, icon: '⏰', color: '#f59e0b' },
    { label: 'Open Violations', value: summary.open_violations, icon: '⚠️', color: '#ef4444' },
    { label: 'Active Projects', value: summary.active_projects, icon: '🚧', color: '#06b6d4' },
  ];

  const pieData = [
    { name: 'Compliant', value: Math.round(summary.compliance_rate * summary.total_subcontractors / 100) },
    { name: 'Non-Compliant', value: summary.total_subcontractors - Math.round(summary.compliance_rate * summary.total_subcontractors / 100) }
  ];

  return (
    <div className="dashboard">
      <OnboardingChecklist />
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <div className="dashboard-nav">
          <span>Overview</span>
        </div>
      </div>

      <div className="dashboard-content">
        <div className="metrics-grid">
          {metrics.map((metric, index) => (
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
                <h2>Compliance Trends (30 Days)</h2>
                <div className="chart-controls">
                  <span className="chart-legend">
                    <span className="legend-dot" style={{ background: '#3b82f6' }}></span>Compliance %
                    <span className="legend-dot" style={{ background: '#ef4444' }}></span>Violations
                    <span className="legend-dot" style={{ background: '#f59e0b' }}></span>Expiring
                  </span>
                </div>
              </div>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={pagedTrendData} onClick={handleChartClick}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} />
                    <Tooltip
                      contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                    />
                    <Line type="monotone" dataKey="compliance" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4, cursor: 'pointer' }} activeDot={{ r: 6 }} />
                    <Line type="monotone" dataKey="violations" stroke="#ef4444" strokeWidth={2} dot={{ r: 4, cursor: 'pointer' }} activeDot={{ r: 6 }} />
                    <Line type="monotone" dataKey="expiring" stroke="#f59e0b" strokeWidth={2} dot={{ r: 4, cursor: 'pointer' }} activeDot={{ r: 6 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              
              {/* Pagination Controls */}
              <div className="pagination-controls">
                <button 
                  className="pagination-btn" 
                  onClick={handlePrevTrend} 
                  disabled={!canPrevTrend}
                >
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  Previous
                </button>
                <span className="pagination-info">
                  Page {trendPage + 1} of {totalTrendPages || 1}
                </span>
                <button 
                  className="pagination-btn" 
                  onClick={handleNextTrend} 
                  disabled={!canNextTrend}
                >
                  Next
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>

              {/* Item Detail Tab */}
              {selectedPoint && (
                <div className="item-detail-tab">
                  <div className="detail-tab-header">
                    <h3>Details for {selectedPoint.date}</h3>
                    <button className="close-detail-btn" onClick={() => setSelectedPoint(null)}>×</button>
                  </div>
                  <div className="detail-tab-content">
                    <div className="detail-row">
                      <span className="detail-label">Compliance</span>
                      <span className="detail-value" style={{ color: '#3b82f6' }}>{selectedPoint.compliance}%</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Violations</span>
                      <span className="detail-value" style={{ color: '#ef4444' }}>{selectedPoint.violations}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Expiring</span>
                      <span className="detail-value" style={{ color: '#f59e0b' }}>{selectedPoint.expiring}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="charts-row">
              <div className="chart-section half">
                <h2>Compliance Distribution</h2>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {pieData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pie-legend">
                  {pieData.map((entry, index) => (
                    <div key={index} className="legend-item">
                      <span className="legend-dot" style={{ background: COLORS[index] }}></span>
                      {entry.name}: {entry.value}
                    </div>
                  ))}
                </div>
              </div>

              <div className="chart-section half">
                <h2>Quick Stats</h2>
                <div className="quick-stats">
                  <div className="stat-row">
                    <span>Total Projects</span>
                    <span className="stat-value">{summary.total_projects}</span>
                  </div>
                  <div className="stat-row">
                    <span>Open Violations</span>
                    <span className="stat-value stat-danger">{summary.open_violations}</span>
                  </div>
                  <div className="stat-row">
                    <span>Expiring (30d)</span>
                    <span className="stat-value stat-warning">{summary.expiring_this_month}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="export-section">
              <h2>Export Reports</h2>
              <div className="export-controls">
                <select
                  value={exportRange}
                  onChange={(e) => setExportRange(e.target.value as '30' | '60' | '90')}
                  className="export-select"
                >
                  <option value="30">Last 30 days</option>
                  <option value="60">Last 60 days</option>
                  <option value="90">Last 90 days</option>
                </select>
                <button className="export-btn" onClick={handleExportCSV}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download CSV
                </button>
              </div>
            </div>
          </div>

          <div className="dashboard-sidebar">
            <div className="alerts-section">
              <h2>Recent Alerts</h2>
              {alerts.length === 0 ? (
                <EmptyState
                  title="No active alerts"
                  description="All subcontractors are in good standing."
                  icon={
                    <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  }
                />
              ) : (
                <div className="alerts-list">
                  {alerts.slice(0, 5).map((alert, index) => (
                    <div
                      key={index}
                      className={`alert-item ${alert.type}`}
                      onClick={() => handleAlertClick(alert)}
                    >
                      <span className={`alert-status ${alert.type}`}>
                        {alert.type === 'critical' ? '🔴' : '🟡'}
                      </span>
                      <div className="alert-content">
                        <p className="alert-message">{alert.message}</p>
                        {alert.days_until_expiration !== undefined && (
                          <span className="alert-days">
                            {alert.days_until_expiration} days remaining
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="quick-actions">
              <h2>Quick Actions</h2>
              <div className="action-buttons">
                <button className="action-btn" onClick={() => window.location.href = '/subcontractors/import'}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add Subcontractor
                </button>
                <button className="action-btn" onClick={() => window.location.href = '/certifications'}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  View Certifications
                </button>
                <button className="action-btn" onClick={() => window.location.href = '/violations'}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  Review Violations
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
