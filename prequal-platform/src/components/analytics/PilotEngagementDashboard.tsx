import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  analyticsApi,
  AnalyticsEventRecord,
} from '../../api/client';
import { useDashboardData } from '../../hooks/useDashboardData';
import type { RealtimeConnectionState } from '../../hooks/useRealtimeConnection';
import { useDashboardTheme } from '../../hooks/useDashboardTheme';
import { isAdmin } from '../../utils/auth';
import { exportRowsToCsv, exportPageToPdf } from '../../utils/exportUtils';
import { Card } from '../ui';
import { Button } from '../ui';
import { Select } from '../ui';
import { Input } from '../ui';
import { Table, type TableColumn } from '../ui';
import MetricCard from './MetricCard';
import LiveIndicator from './LiveIndicator';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar,
} from 'recharts';

const formatNumber = (value?: number | null): string =>
  value !== undefined && value !== null ? value.toLocaleString('en-US') : '—';

const formatPercent = (value?: number | null): string =>
  value !== undefined && value !== null ? `${Number(value).toFixed(1)}%` : '—';

const EVENT_TYPE_OPTIONS = [
  { value: '', label: 'All event types' },
  { value: 'page_view', label: 'Page view' },
  { value: 'feature_usage', label: 'Feature usage' },
  { value: 'onboarding_completion', label: 'Onboarding completion' },
  { value: 'subcontractor_added', label: 'Subcontractor added' },
  { value: 'subcontractor_updated', label: 'Subcontractor updated' },
  { value: 'subcontractor_removed', label: 'Subcontractor removed' },
  { value: 'cert_uploaded', label: 'Cert uploaded' },
  { value: 'feedback_submitted', label: 'Feedback submitted' },
];

interface Props {
  realtime: RealtimeConnectionState;
}

const PilotEngagementDashboard: React.FC<Props> = ({ realtime }) => {
  const { chartColors } = useDashboardTheme();
  const admin = isAdmin();

  const [days, setDays] = useState('30');
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [orgFilter, setOrgFilter] = useState('');

  const realtimeLive = realtime.mode === 'websocket' && realtime.connected;

  const engagement = useDashboardData(
    useCallback(() => analyticsApi.getPilotEngagement(Number(days)), [days]),
    { refreshIntervalMs: 30000, isRealtimeLive: realtimeLive },
  );
  const dau = useDashboardData(
    useCallback(() => analyticsApi.getDailyActiveUsers(Number(days)), [days]),
    { refreshIntervalMs: 30000, isRealtimeLive: realtimeLive },
  );
  const events = useDashboardData(
    useCallback(
      () =>
        analyticsApi.getEvents({
          days: Number(days),
          limit: 50,
          ...(eventTypeFilter && { event_type: eventTypeFilter }),
          ...(admin && orgFilter.trim() && { organization_id: orgFilter.trim() }),
        }),
      [days, eventTypeFilter, orgFilter, admin],
    ),
    { refreshIntervalMs: 15000, isRealtimeLive: realtimeLive },
  );

  const refetchAll = useCallback(() => {
    engagement.refetch();
    dau.refetch();
    events.refetch();
  }, [engagement, dau, events]);

  useEffect(() => {
    if (realtime.lastMessageAt) refetchAll();
  }, [realtime.lastMessageAt, refetchAll]);

  const engagementData = engagement.data;
  const dauData = dau.data ?? [];
  const eventRows = events.data ?? [];

  const dauChart = useMemo(
    () =>
      [...dauData]
        .sort((a, b) => a.day.localeCompare(b.day))
        .map((point) => ({
          day: new Date(point.day).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
          activeUsers: point.active_users,
        })),
    [dauData],
  );

  const trendChart = useMemo(
    () =>
      (engagementData?.engagement_trends ?? []).map((t) => ({
        date: new Date(t.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        activeOrganizations: t.active_organizations,
        totalEvents: t.total_events,
      })),
    [engagementData],
  );

  const latestDau = dauChart.length > 0 ? dauChart[dauChart.length - 1].activeUsers : null;
  const previousDau = dauChart.length > 1 ? dauChart[dauChart.length - 2].activeUsers : null;
  const dauTrend =
    latestDau !== null && previousDau !== null && previousDau > 0
      ? latestDau >= previousDau
        ? ('up' as const)
        : ('down' as const)
      : null;

  const monthlyActive = engagementData?.active_users_30d ?? null;
  const dauMauRatio =
    latestDau !== null && monthlyActive && monthlyActive > 0
      ? `${((latestDau / monthlyActive) * 100).toFixed(1)}%`
      : '—';

  const handleExportCsv = () => {
    exportRowsToCsv(
      'pilot_engagement',
      `pilot-engagement-${new Date().toISOString().slice(0, 10)}`,
      ['id', 'event_type', 'user_id', 'organization_id', 'created_at'],
      eventRows.map((event) => ({
        id: event.id,
        event_type: event.event_type,
        user_id: event.user_id ?? '',
        organization_id: event.organization_id ?? '',
        created_at: event.created_at,
      })),
    );
  };

  const eventColumns: TableColumn<AnalyticsEventRecord & Record<string, unknown>>[] = [
    {
      key: 'event_type',
      header: 'Event type',
      render: (value) => String(value ?? '').replace(/_/g, ' '),
    },
    {
      key: 'organization_id',
      header: 'Organization',
      render: (value) => (value === null || value === undefined || value === '' ? '—' : String(value)),
    },
    {
      key: 'user_id',
      header: 'User',
      render: (value) => (value === null || value === undefined || value === '' ? 'Anonymous' : String(value)),
    },
    { key: 'created_at', header: 'When' },
  ];

  return (
    <div className="analytics-page" data-testid="pilot-engagement-dashboard">
      <div className="analytics-toolbar">
        <div className="analytics-filters">
          <Select
            options={[
              { value: '7', label: 'Last 7 days' },
              { value: '30', label: 'Last 30 days' },
              { value: '90', label: 'Last 90 days' },
            ]}
            value={days}
            onChange={setDays}
            label="Date range"
          />
          <Select
            options={EVENT_TYPE_OPTIONS}
            value={eventTypeFilter}
            onChange={setEventTypeFilter}
            label="Event type"
          />
          {admin && (
            <Input
              value={orgFilter}
              onChange={(e) => setOrgFilter(e.target.value)}
              placeholder="Filter by organization ID"
              aria-label="Filter by organization ID"
              label="Organization"
            />
          )}
          {!admin && (
            <span className="scope-badge" title="Data is scoped to your organization">
              Org-scoped
            </span>
          )}
        </div>
        <div className="analytics-actions">
          <LiveIndicator connection={realtime} />
          <Button size="sm" onClick={refetchAll} aria-label="Refresh pilot engagement data">
            ↻ Refresh
          </Button>
          <Button size="sm" variant="secondary" onClick={handleExportCsv} aria-label="Export events as CSV">
            ⬇ CSV
          </Button>
          <Button size="sm" variant="secondary" onClick={() => exportPageToPdf('pilot_engagement')} aria-label="Print dashboard as PDF">
            🖨 PDF
          </Button>
        </div>
      </div>

      <div className="analytics-metric-grid">
        <MetricCard label="Total Organizations" value={formatNumber(engagementData?.total_organizations)} icon="🏢" accent={chartColors.primary} />
        <MetricCard label="Active Orgs (30d)" value={formatNumber(engagementData?.active_organizations_30d)} icon="📈" accent={chartColors.info} />
        <MetricCard label="Total Users" value={formatNumber(engagementData?.total_users)} icon="👥" accent={chartColors.secondary} hint="Resolved cross-service" />
        <MetricCard label="Active Users (30d)" value={formatNumber(engagementData?.active_users_30d)} icon="✅" accent={chartColors.success} />
        <MetricCard
          label="Daily Active Users"
          value={formatNumber(latestDau)}
          icon="📅"
          accent={chartColors.warning}
          trend={dauTrend}
          trendLabel={latestDau !== null ? `vs ${formatNumber(previousDau)} yesterday` : undefined}
        />
        <MetricCard label="DAU / MAU Ratio" value={dauMauRatio} icon="📊" accent={chartColors.danger} hint="Engagement stickiness" />
        <MetricCard label="Avg Events / Org" value={formatNumber(engagementData?.avg_events_per_org)} icon="⚡" accent={chartColors.primary} />
        <MetricCard label="Onboarding Completion" value={formatPercent(engagementData?.onboarding_completion_rate)} icon="🎓" accent={chartColors.success} />
      </div>

      <div className="analytics-grid">
        <Card title="Engagement Trends" description="Active organizations and total events per day">
          <div className="analytics-chart-container">
            {trendChart.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={trendChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                  <XAxis dataKey="date" stroke={chartColors.axis} fontSize={12} />
                  <YAxis stroke={chartColors.axis} fontSize={12} />
                  <Tooltip contentStyle={{ background: chartColors.tooltipBg, border: `1px solid ${chartColors.tooltipBorder}`, borderRadius: '8px' }} />
                  <Legend />
                  <Area type="monotone" dataKey="activeOrganizations" name="Active Organizations" stroke={chartColors.primary} fill={chartColors.primary} fillOpacity={0.2} strokeWidth={2} />
                  <Area type="monotone" dataKey="totalEvents" name="Total Events" stroke={chartColors.success} fill={chartColors.success} fillOpacity={0.2} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="no-data-message">No engagement trend data available.</p>
            )}
          </div>
        </Card>

        <Card title="Daily Active Users" description="Unique active users per day">
          <div className="analytics-chart-container">
            {dauChart.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={dauChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                  <XAxis dataKey="day" stroke={chartColors.axis} fontSize={12} />
                  <YAxis stroke={chartColors.axis} fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: chartColors.tooltipBg, border: `1px solid ${chartColors.tooltipBorder}`, borderRadius: '8px' }} />
                  <Bar dataKey="activeUsers" name="Active Users" fill={chartColors.secondary} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="no-data-message">No daily active user data available.</p>
            )}
          </div>
        </Card>
      </div>

      <Card
        title="Live Event Stream"
        description="Latest analytics events from the ingestion pipeline"
        action={
          <span className="live-event-count" aria-live="polite">
            {events.loading ? 'Loading…' : `${eventRows.length} events`}
          </span>
        }
      >
        <Table
          columns={eventColumns}
          data={eventRows.map((event) => ({ ...event, created_at: new Date(event.created_at).toLocaleString('en-US') }))}
          keyExtractor={(row) => row.id}
          loading={events.loading && eventRows.length === 0}
          emptyMessage="No events recorded in this period."
        />
        {events.error && <p className="analytics-error" role="alert">{events.error}</p>}
      </Card>
    </div>
  );
};

export default PilotEngagementDashboard;
