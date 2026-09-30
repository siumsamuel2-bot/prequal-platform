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
import { useToast } from './ToastContext';
import { Link } from 'react-router-dom';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Legend,
} from 'recharts';
import './Dashboard.css';

const formatNumber = (value?: number | null): string =>
  value !== undefined && value !== null ? value.toLocaleString('en-US') : '—';

const formatPercent = (value?: number | null): string =>
  value !== undefined && value !== null ? `${Number(value).toFixed(1)}%` : '—';

const formatMs = (value?: number | null): string =>
  value !== undefined && value !== null ? `${Number(value).toFixed(0)}ms` : '—';

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

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      analyticsApi.getPilotEngagement(30),
      analyticsApi.getFeatureAdoption({ days: 30 }),
      analyticsApi.getSystemHealth(),
      analyticsApi.getPerformanceMetrics(),
      billingApi.getSubscription(),
      billingApi.getPlans(),
    ]);

    const [engagementResult, adoptionResult, healthResult, performanceResult, subscriptionResult, plansResult] = results;

    if (engagementResult.status === 'fulfilled') {
      setEngagement(engagementResult.value);
    } else {
      toast.error('Failed to load user growth metrics');
    }

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

    if (subscriptionResult.status === 'fulfilled') {
      setSubscription(subscriptionResult.value);
    } else {
      toast.error('Failed to load subscription data');
    }

    if (plansResult.status === 'fulfilled') {
      setPlans(plansResult.value ?? []);
    }

    setLoading(false);
    setLastRefreshed(new Date());
  }, [toast]);

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
  }));

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
    { label: 'API Error Rate', value: formatPercent(performance?.error_rate_percent), icon: '⚠️', color: (performance?.error_rate_percent ?? 0) > 5 ? '#ef4444' : '#10b981' },
    { label: 'Avg Response Time', value: formatMs(performance?.avg_response_time_ms), icon: '⏱️', color: '#0ea5e9' },
  ];

  if (loading && !lastRefreshed) {
    return (
      <div className="dashboard">
        <Loading message="Loading analytics..." fullScreen />
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
                ) : (
                  <p className="no-data-message">No engagement trend data available.</p>
                )}
              </div>
            </div>

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

            <div className="charts-row">
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
              </div>

              <div className="chart-section half">
                <h2>System Health by Service</h2>
                {servicesData.length > 0 ? (
                  <div className="quick-stats">
                    {servicesData.slice(0, 6).map((s) => (
                      <div key={s.name} className="stat-row">
                        <span>{s.name}</span>
                        <span className="stat-value">
                          avg {s.avgValue}
                          {s.unit} · p95 {s.p95Value}
                          {s.unit}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="no-data-message">No system health data available.</p>
                )}
              </div>
            </div>
          </div>

          <div className="dashboard-sidebar">
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
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
