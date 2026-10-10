import React, { useState, useEffect, useCallback } from 'react';
import {
  analyticsApi,
  billingApi,
  PilotEngagementData,
  FeatureAdoptionData,
  SystemHealthData,
  PerformanceMetricsData,
  SubscriptionStatus,
  BillingPlan,
} from '../api/client';
import { Loading } from './Loading';
import { NoAccessState, isForbiddenError } from './NoAccessState';
import { isAdmin } from '../utils/auth';
import FeedbackWidget from './FeedbackWidget';
import { useToast } from './ToastContext';
import { Link } from 'react-router-dom';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Legend,
  PieChart, Pie, Cell,
} from 'recharts';
import './Dashboard.css';

const formatNumber = (value?: number | null): string =>
  value !== undefined && value !== null ? value.toLocaleString('en-US') : '—';

const formatPercent = (value?: number | null): string =>
  value !== undefined && value !== null ? `${Number(value).toFixed(1)}%` : '—';

const formatMs = (value?: number | null): string =>
  value !== undefined && value !== null ? `${Number(value).toFixed(0)}ms` : '—';

const parsePrice = (price: string): number | null => {
  const match = /\$?\s*([\d,]+(?:\.\d+)?)/.exec(price);
  if (!match) return null;
  const value = parseFloat(match[1].replace(/,/g, ''));
  return Number.isFinite(value) ? value : null;
};

type HealthStatus = 'healthy' | 'warning' | 'critical';

const HEALTH_STATUS_LABELS: Record<HealthStatus, string> = {
  healthy: 'Healthy',
  warning: 'Warning',
  critical: 'Critical',
};

const getHealthStatus = (service: SystemHealthData): HealthStatus => {
  const unit = (service.metric_unit ?? '').toLowerCase();
  if (unit === 'ms') {
    if (service.p95_value >= 1000) return 'critical';
    if (service.p95_value >= 500) return 'warning';
    return 'healthy';
  }
  if (unit === '%' || unit === 'percent') {
    if (service.p95_value >= 95) return 'critical';
    if (service.p95_value >= 80) return 'warning';
    return 'healthy';
  }
  return 'healthy';
};

const getOverallHealthStatus = (services: SystemHealthData[]): HealthStatus => {
  const statuses = services.map(getHealthStatus);
  if (statuses.includes('critical')) return 'critical';
  if (statuses.includes('warning')) return 'warning';
  return 'healthy';
};

const PIE_COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4'];

const AnalyticsDashboard: React.FC = () => {
  const toast = useToast();
  const [engagement, setEngagement] = useState<PilotEngagementData | null>(null);
  const [featureAdoption, setFeatureAdoption] = useState<FeatureAdoptionData[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealthData[]>([]);
  const [performance, setPerformance] = useState<PerformanceMetricsData | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [engagementDenied, setEngagementDenied] = useState(false);

  const isAdminUser = isAdmin();

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      analyticsApi.getPilotEngagement(30),
      billingApi.getSubscription(),
      billingApi.getPlans(),
    ]);

    const [engagementResult, subscriptionResult, plansResult] = results;

    if (engagementResult.status === 'fulfilled') {
      setEngagement(engagementResult.value);
      setEngagementDenied(false);
    } else if (isForbiddenError(engagementResult.reason) && !isAdminUser) {
      // Fail-closed 403 for this account (no resolvable team): show the calm
      // no-access state instead of an alarming error toast (MID-657).
      setEngagement(null);
      setEngagementDenied(true);
    } else {
      setEngagementDenied(false);
      toast.error('Failed to load user growth metrics');
    }

    if (subscriptionResult.status === 'fulfilled') {
      setSubscription(subscriptionResult.value);
    } else {
      toast.error('Failed to load subscription data');
    }

    if (plansResult.status === 'fulfilled') {
      setPlans(plansResult.value ?? []);
    }

    // Platform-only aggregates are admin-only since MID-650; skip the fetch
    // entirely for non-admins instead of showing the panels failing.
    if (isAdminUser) {
      const adminResults = await Promise.allSettled([
        analyticsApi.getFeatureAdoption({ days: 30 }),
        analyticsApi.getSystemHealth(),
        analyticsApi.getPerformanceMetrics(),
      ]);

      const [adoptionResult, healthResult, performanceResult] = adminResults;

      if (adoptionResult.status === 'fulfilled') {
        setFeatureAdoption(adoptionResult.value ?? []);
      } else {
        toast.error('Failed to load feature adoption metrics');
      }

      if (healthResult.status === 'fulfilled') {
        setSystemHealth(healthResult.value ?? []);
      } else {
        toast.error('Failed to load system health metrics');
      }

      if (performanceResult.status === 'fulfilled') {
        setPerformance(performanceResult.value);
      } else {
        toast.error('Failed to load performance metrics');
      }
    } else {
      setFeatureAdoption([]);
      setSystemHealth([]);
      setPerformance(null);
    }

    setLoading(false);
    setLastRefreshed(new Date());
  }, [toast, isAdminUser]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  const currentPlan = plans.find((p) => p.plan === subscription?.plan);
  const seatUtilization = subscription && subscription.subcontractor_limit > 0
    ? Math.round((subscription.subcontractor_count / subscription.subcontractor_limit) * 100)
    : null;

  const engagementTrendData = (engagement?.engagement_trends ?? []).map((t) => ({
    date: new Date(t.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    activeOrganizations: t.active_organizations,
    totalEvents: t.total_events,
  }));

  const featureAdoptionData = [...featureAdoption]
    .sort((a, b) => b.total_events - a.total_events)
    .slice(0, 8)
    .map((f) => ({
      name: f.feature_name,
      totalEvents: f.total_events,
      uniqueUsers: f.unique_users,
    }));

  const servicesData = systemHealth.map((s) => ({
    name: `${s.service_name} — ${s.metric_name}`,
    p95Value: s.p95_value,
    avgValue: s.avg_value,
    unit: s.metric_unit ?? '',
    status: getHealthStatus(s),
  }));

  const overallHealthStatus = getOverallHealthStatus(systemHealth);

  const revenueDistributionData = plans
    .map((p) => ({ name: p.name, value: parsePrice(p.price) }))
    .filter((entry): entry is { name: string; value: number } => entry.value !== null && entry.value > 0);

  const kpiCards = [
    { label: 'Total Users', value: formatNumber(engagement?.total_users), icon: '👥', color: '#3b82f6' },
    { label: 'Active Users (30d)', value: formatNumber(engagement?.active_users_30d), icon: '✅', color: '#10b981' },
    { label: 'Total Organizations', value: formatNumber(engagement?.total_organizations), icon: '🏢', color: '#8b5cf6' },
    { label: 'Active Organizations (30d)', value: formatNumber(engagement?.active_organizations_30d), icon: '📈', color: '#06b6d4' },
    { label: 'Onboarding Completion', value: formatPercent(engagement?.onboarding_completion_rate), icon: '🎓', color: '#f59e0b' },
    {
      label: 'Current Plan',
      value: subscription && currentPlan ? `${currentPlan.name} (${currentPlan.price})` : subscription?.plan ?? '—',
      icon: '💳',
      color: '#ec4899',
    },
    { label: 'Seat Utilization', value: seatUtilization !== null ? `${seatUtilization}%` : '—', icon: '🔐', color: '#6366f1' },
    // Performance metrics are admin-only; hidden for non-admins (MID-657).
    ...(isAdminUser
      ? [
          { label: 'API Error Rate', value: formatPercent(performance?.error_rate_percent), icon: '⚠️', color: (performance?.error_rate_percent ?? 0) > 5 ? '#ef4444' : '#10b981' },
          { label: 'Avg Response Time', value: formatMs(performance?.avg_response_time_ms), icon: '⏱️', color: '#0ea5e9' },
        ]
      : []),
  ];

  if (loading && !lastRefreshed) {
    return (
      <div className="dashboard">
        <Loading message="Loading analytics..." fullScreen />
      </div>
    );
  }

  if (engagementDenied && !isAdminUser) {
    return (
      <div className="dashboard">
        <div className="dashboard-header" style={{ backgroundColor: '#0ea5e9' }}>
          <h1>Analytics Dashboard</h1>
          <div className="dashboard-nav">
            <span>Platform Growth & System Health</span>
            <button
              className="action-btn"
              onClick={loadAnalytics}
              disabled={loading}
              aria-label="Refresh analytics data"
            >
              {loading ? 'Refreshing...' : '↻ Refresh'}
            </button>
          </div>
        </div>
        <div className="dashboard-content">
          <NoAccessState variant="no-access" />
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header" style={{ backgroundColor: '#0ea5e9' }}>
        <h1>Analytics Dashboard</h1>
        <div className="dashboard-nav">
          <span>Platform Growth & System Health</span>
          <button
            className="action-btn"
            onClick={loadAnalytics}
            disabled={loading}
            aria-label="Refresh analytics data"
          >
            {loading ? 'Refreshing...' : '↻ Refresh'}
          </button>
        </div>
      </div>

      <div className="dashboard-content">
        <div className="metrics-grid">
          {kpiCards.map((metric) => (
            <div key={metric.label} className="metric-card" style={{ borderLeftColor: metric.color }}>
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
                <h2>User Growth & Engagement Trends</h2>
              </div>
              <div className="chart-container">
                {engagementTrendData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <AreaChart data={engagementTrendData}>
                      <defs>
                        <linearGradient id="orgGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1} />
                        </linearGradient>
                        <linearGradient id="eventGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.8} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0.1} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                      <YAxis stroke="#6b7280" fontSize={12} />
                      <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }} />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="activeOrganizations"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        fill="url(#orgGradient)"
                        name="Active Organizations"
                      />
                      <Area
                        type="monotone"
                        dataKey="totalEvents"
                        stroke="#10b981"
                        strokeWidth={2}
                        fill="url(#eventGradient)"
                        name="Total Events"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : isAdminUser ? (
                  <p className="no-data-message">No engagement trend data available.</p>
                ) : (
                  <NoAccessState variant="no-data" />
                )}
              </div>
            </div>

            {!isAdminUser ? null : (
            <div className="chart-section">
              <div className="section-header">
                <h2>Feature Adoption (Last 30 Days)</h2>
              </div>
              <div className="chart-container">
                {featureAdoptionData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={featureAdoptionData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
                      <YAxis stroke="#6b7280" fontSize={12} />
                      <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }} />
                      <Legend />
                      <Bar dataKey="totalEvents" fill="#3b82f6" name="Total Events" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="uniqueUsers" fill="#8b5cf6" name="Unique Users" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="no-data-message">No feature adoption data available.</p>
                )}
              </div>
            </div>
            )}

            <div className="charts-row" style={isAdminUser ? undefined : { gridTemplateColumns: '1fr' }}>
              <div className="chart-section half">
                <h2>Revenue & Subscription</h2>
                <div className="quick-stats">
                  <div className="stat-row">
                    <span>Plan</span>
                    <span className="stat-value">{currentPlan?.name ?? subscription?.plan ?? '—'}</span>
                  </div>
                  <div className="stat-row">
                    <span>Monthly Price</span>
                    <span className="stat-value">{currentPlan?.price ?? '—'}</span>
                  </div>
                  <div className="stat-row">
                    <span>Subscription Status</span>
                    <span
                      className={`stat-value ${
                        subscription?.status === 'active' ? '' : subscription?.status === 'past_due' ? 'stat-danger' : 'stat-warning'
                      }`}
                    >
                      {subscription?.status ?? '—'}
                    </span>
                  </div>
                  <div className="stat-row">
                    <span>Seats Used</span>
                    <span className="stat-value">
                      {subscription ? `${subscription.subcontractor_count}/${subscription.subcontractor_limit}` : '—'}
                    </span>
                  </div>
                  <div className="stat-row">
                    <span>Seat Utilization</span>
                    <span className={`stat-value ${seatUtilization !== null && seatUtilization > 90 ? 'stat-danger' : ''}`}>
                      {seatUtilization !== null ? `${seatUtilization}%` : '—'}
                    </span>
                  </div>
                  <div className="stat-row">
                    <span>Renews</span>
                    <span className="stat-value">
                      {subscription?.current_period_end
                        ? new Date(subscription.current_period_end).toLocaleDateString('en-US')
                        : '—'}
                    </span>
                  </div>
                </div>
                {revenueDistributionData.length > 0 ? (
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height={200}>
                      <PieChart>
                        <Pie
                          data={revenueDistributionData}
                          cx="50%"
                          cy="50%"
                          innerRadius={55}
                          outerRadius={85}
                          paddingAngle={2}
                          dataKey="value"
                          nameKey="name"
                        >
                          {revenueDistributionData.map((entry, index) => (
                            <Cell key={`revenue-cell-${entry.name}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                          formatter={(value) => [`$${Number(value).toLocaleString('en-US')}/month`, 'Monthly Price']}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="pie-legend">
                      {revenueDistributionData.map((entry, index) => (
                        <span key={entry.name} className="legend-item">
                          <span
                            className="legend-dot"
                            style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }}
                            aria-hidden="true"
                          />
                          {entry.name}
                          {entry.name === currentPlan?.name ? ' (current)' : ''}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="no-data-message">No revenue distribution data available.</p>
                )}
              </div>

              {isAdminUser ? (
              <div className="chart-section half">
                <div className="section-header">
                  <h2>System Health by Service</h2>
                  {servicesData.length > 0 && (
                    <span
                      className={`health-badge ${overallHealthStatus}`}
                      role="status"
                      aria-label={`Overall system status: ${HEALTH_STATUS_LABELS[overallHealthStatus]}`}
                    >
                      {HEALTH_STATUS_LABELS[overallHealthStatus]}
                    </span>
                  )}
                </div>
                {servicesData.length > 0 ? (
                  <div className="quick-stats">
                    {servicesData.slice(0, 6).map((s) => (
                      <div key={s.name} className="stat-row">
                        <span className="health-service-label">
                          <span className={`health-dot ${s.status}`} aria-hidden="true" />
                          <span className="health-service-text">
                            <span className="health-service-name">{s.name}</span>
                            <span className="health-service-metrics">
                              avg {s.avgValue}
                              {s.unit} · p95 {s.p95Value}
                              {s.unit}
                            </span>
                          </span>
                        </span>
                        <span
                          className={`health-badge ${s.status}`}
                          role="status"
                          aria-label={`${s.name} health status: ${HEALTH_STATUS_LABELS[s.status]}`}
                        >
                          {HEALTH_STATUS_LABELS[s.status]}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="no-data-message">No system health data available.</p>
                )}
              </div>
              ) : null}
            </div>
          </div>

          <div className="dashboard-sidebar">
            {isAdminUser ? (
            <div className="chart-section">
              <h2>Performance Summary</h2>
              <div className="quick-stats">
                <div className="stat-row">
                  <span>Requests/sec</span>
                  <span className="stat-value">
                    {performance ? performance.requests_per_second.toFixed(2) : '—'}
                  </span>
                </div>
                <div className="stat-row">
                  <span>Error Rate</span>
                  <span className={`stat-value ${(performance?.error_rate_percent ?? 0) > 1 ? 'stat-danger' : ''}`}>
                    {formatPercent(performance?.error_rate_percent)}
                  </span>
                </div>
                <div className="stat-row">
                  <span>p50 Response</span>
                  <span className="stat-value" style={{ color: '#10b981' }}>
                    {formatMs(performance?.p50_response_time_ms)}
                  </span>
                </div>
                <div className="stat-row">
                  <span>p95 Response</span>
                  <span className="stat-value" style={{ color: '#f59e0b' }}>
                    {formatMs(performance?.p95_response_time_ms)}
                  </span>
                </div>
                <div className="stat-row">
                  <span>DB Connections</span>
                  <span className="stat-value">
                    {performance ? `${performance.active_db_connections}/${performance.max_db_connections}` : '—'}
                  </span>
                </div>
                <div className="stat-row">
                  <span>Last Refreshed</span>
                  <span className="stat-value">
                    {lastRefreshed ? lastRefreshed.toLocaleTimeString('en-US') : '—'}
                  </span>
                </div>
              </div>
            </div>
            ) : null}

            <div className="chart-section">
              <h2>Recently Active Organizations</h2>
              {(engagement?.recently_active_orgs ?? []).length > 0 ? (
                <div className="quick-stats">
                  {engagement?.recently_active_orgs.slice(0, 6).map((org) => (
                    <div key={org.organization_id} className="stat-row">
                      <span>{org.organization_name}</span>
                      <span className="stat-value">
                        {new Date(org.last_activity).toLocaleDateString('en-US')}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="no-data-message">No recent organization activity.</p>
              )}
            </div>

            <div className="quick-actions">
              <h2>Quick Actions</h2>
              <div className="action-buttons">
                <Link className="action-btn" to="/dashboard">
                  ← Back to Dashboard
                </Link>
                <Link className="action-btn" to="/performance-dashboard">
                  ⚡ Performance Dashboard
                </Link>
                <Link className="action-btn" to="/compliance-dashboard">
                  🛡️ Compliance Dashboard
                </Link>
                <Link className="action-btn" to="/support">
                  💬 Support & Known Issues
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
      <FeedbackWidget surface="analytics_dashboard" />
    </div>
  );
};

export default AnalyticsDashboard;
