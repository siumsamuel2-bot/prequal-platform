import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { subcontractorApi, complianceAnalyticsApi, Subcontractor, ComplianceTrendPoint } from '../../api/client';
import { useDashboardData } from '../../hooks/useDashboardData';
import type { RealtimeConnectionState } from '../../hooks/useRealtimeConnection';
import { useDashboardTheme } from '../../hooks/useDashboardTheme';
import { exportRowsToCsv, exportPageToPdf } from '../../utils/exportUtils';
import { Card, Button, Input, Select, Badge, Table, type TableColumn } from '../ui';
import MetricCard from './MetricCard';
import LiveIndicator from './LiveIndicator';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

const formatNumber = (value?: number | null): string =>
  value !== undefined && value !== null ? value.toLocaleString('en-US') : '—';

const formatPercent = (value?: number | null): string =>
  value !== undefined && value !== null ? `${Number(value).toFixed(1)}%` : '—';

/**
 * Status-derived risk tier. The analytics service does not compute a
 * per-subcontractor risk score yet; tiers are derived from the account
 * status until that metric ships (see docs/ANALYTICS_DASHBOARD.md).
 */
type RiskTier = 'standard' | 'elevated' | 'high';

const RISK_TIER: Record<string, RiskTier> = {
  active: 'standard',
  suspended: 'high',
  blacklisted: 'high',
};

const RISK_BADGE_VARIANT: Record<RiskTier, 'success' | 'warning' | 'danger'> = {
  standard: 'success',
  elevated: 'warning',
  high: 'danger',
};

const getRiskTier = (subcontractor: Subcontractor): RiskTier =>
  RISK_TIER[(subcontractor.status ?? '').toLowerCase()] ?? 'elevated';

const getTrade = (subcontractor: Subcontractor): string => {
  const record = subcontractor as unknown as Record<string, unknown>;
  const trade = record.trade;
  return typeof trade === 'string' && trade ? trade : 'Unspecified';
};

interface Props {
  realtime: RealtimeConnectionState;
}

const SubcontractorAnalyticsDashboard: React.FC<Props> = ({ realtime }) => {
  const { chartColors } = useDashboardTheme();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [days, setDays] = useState('30');

  const realtimeLive = realtime.mode === 'websocket' && realtime.connected;

  const subcontractors = useDashboardData(
    useCallback(() => subcontractorApi.getAll(), []),
    { refreshIntervalMs: 60000, isRealtimeLive: realtimeLive },
  );
  const summary = useDashboardData(
    useCallback(() => complianceAnalyticsApi.getSummary(), []),
    { refreshIntervalMs: 60000, isRealtimeLive: realtimeLive },
  );
  const trends = useDashboardData(
    useCallback(() => complianceAnalyticsApi.getTrends(Number(days)), [days]),
    { refreshIntervalMs: 60000, isRealtimeLive: realtimeLive },
  );

  const refetchAll = useCallback(() => {
    subcontractors.refetch();
    summary.refetch();
    trends.refetch();
  }, [subcontractors, summary, trends]);

  useEffect(() => {
    if (realtime.lastMessageAt) refetchAll();
  }, [realtime.lastMessageAt, refetchAll]);

  const subs: Subcontractor[] = subcontractors.data ?? [];
  const summaryData = summary.data;
  const trendRows: ComplianceTrendPoint[] = trends.data ?? [];

  const filteredRows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return subs.filter((sub) => {
      if (statusFilter && (sub.status ?? '').toLowerCase() !== statusFilter) return false;
      if (!term) return true;
      return (
        sub.company_name.toLowerCase().includes(term) ||
        (sub.email ?? '').toLowerCase().includes(term) ||
        (sub.state ?? '').toLowerCase().includes(term) ||
        getTrade(sub).toLowerCase().includes(term)
      );
    });
  }, [subs, search, statusFilter]);

  const statusDistribution = useMemo(() => {
    const counts = new Map<string, number>();
    subs.forEach((sub) => {
      const status = (sub.status ?? 'unknown').toLowerCase();
      counts.set(status, (counts.get(status) ?? 0) + 1);
    });
    return Array.from(counts.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [subs]);

  const tradeDistribution = useMemo(() => {
    const counts = new Map<string, number>();
    subs.forEach((sub) => {
      const trade = getTrade(sub);
      counts.set(trade, (counts.get(trade) ?? 0) + 1);
    });
    return Array.from(counts.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
  }, [subs]);

  const complianceTrendChart = useMemo(
    () =>
      trendRows.map((point) => ({
        date: point.date
          ? new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
          : '',
        compliancePercentage: point.compliance_percentage,
      })),
    [trendRows],
  );

  const handleExportCsv = () => {
    exportRowsToCsv(
      'subcontractor_analytics',
      `subcontractor-analytics-${new Date().toISOString().slice(0, 10)}`,
      ['company_name', 'trade', 'status', 'state', 'email', 'risk_tier'],
      filteredRows.map((sub) => ({
        company_name: sub.company_name,
        trade: getTrade(sub),
        status: sub.status ?? '',
        state: sub.state ?? '',
        email: sub.email ?? '',
        risk_tier: getRiskTier(sub),
      })),
    );
  };

  const columns: TableColumn<Subcontractor & Record<string, unknown>>[] = [
    { key: 'company_name', header: 'Company' },
    { key: 'trade', header: 'Trade', render: (_value, row) => getTrade(row as Subcontractor) },
    { key: 'state', header: 'State', render: (value) => (value ? String(value) : '—') },
    {
      key: 'status',
      header: 'Status',
      render: (value) => <Badge variant={value === 'active' ? 'success' : value === 'suspended' || value === 'blacklisted' ? 'danger' : 'default'}>{String(value ?? 'unknown')}</Badge>,
    },
    {
      key: 'risk_tier',
      header: 'Risk tier',
      sortable: false,
      render: (_value, row) => {
        const tier = getRiskTier(row as Subcontractor);
        return <Badge variant={RISK_BADGE_VARIANT[tier]} dot>{tier}</Badge>;
      },
    },
  ];

  return (
    <div className="analytics-page" data-testid="subcontractor-analytics-dashboard">
      <div className="analytics-toolbar">
        <div className="analytics-filters">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search company, trade, state…"
            aria-label="Search subcontractors"
            label="Search"
          />
          <Select
            options={[
              { value: '', label: 'All statuses' },
              { value: 'active', label: 'Active' },
              { value: 'suspended', label: 'Suspended' },
              { value: 'blacklisted', label: 'Blacklisted' },
            ]}
            value={statusFilter}
            onChange={setStatusFilter}
            label="Status"
          />
          <Select
            options={[
              { value: '7', label: 'Last 7 days' },
              { value: '30', label: 'Last 30 days' },
              { value: '90', label: 'Last 90 days' },
            ]}
            value={days}
            onChange={setDays}
            label="Trend range"
          />
          <span className="scope-badge" title="Subcontractor data is scoped to your organization (MID-544/545/546/547)">
            Org-scoped
          </span>
        </div>
        <div className="analytics-actions">
          <LiveIndicator connection={realtime} />
          <Button size="sm" onClick={refetchAll} aria-label="Refresh subcontractor analytics">↻ Refresh</Button>
          <Button size="sm" variant="secondary" onClick={handleExportCsv} aria-label="Export subcontractor analytics as CSV">⬇ CSV</Button>
          <Button size="sm" variant="secondary" onClick={() => exportPageToPdf('subcontractor_analytics')} aria-label="Print dashboard as PDF">🖨 PDF</Button>
        </div>
      </div>

      <div className="analytics-metric-grid">
        <MetricCard label="Compliance Rate" value={formatPercent(summaryData?.compliance_rate)} icon="🛡" accent={chartColors.success} />
        <MetricCard label="Compliant Subcontractors" value={formatNumber(summaryData?.compliant_subcontractors)} icon="✅" accent={chartColors.primary} />
        <MetricCard label="Active Subcontractors" value={formatNumber(summaryData?.active_subcontractors)} icon="👷" accent={chartColors.info} />
        <MetricCard label="Suspended" value={formatNumber(summaryData?.suspended_subcontractors)} icon="⛔" accent={chartColors.warning} />
        <MetricCard label="Blacklisted" value={formatNumber(summaryData?.blacklisted_subcontractors)} icon="🚫" accent={chartColors.danger} />
        <MetricCard label="Expiring Certs (30d)" value={formatNumber(summaryData?.expiring_soon_30d)} icon="⏳" accent={chartColors.warning} />
      </div>

      <div className="analytics-grid">
        <Card title="Subcontractor Table" description={`${filteredRows.length} of ${subs.length} subcontractors`}>
          <Table
            columns={columns}
            data={filteredRows as (Subcontractor & Record<string, unknown>)[]}
            keyExtractor={(row) => row.id}
            loading={subcontractors.loading && subs.length === 0}
            emptyMessage="No subcontractors match the current filters."
          />
          {subcontractors.error && <p className="analytics-error" role="alert">{subcontractors.error}</p>}
        </Card>
      </div>

      <div className="analytics-grid">
        <Card title="Status Distribution" description="Subcontractors grouped by account status">
          <div className="analytics-chart-container">
            {statusDistribution.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={statusDistribution}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                  <XAxis dataKey="name" stroke={chartColors.axis} fontSize={12} />
                  <YAxis stroke={chartColors.axis} fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: chartColors.tooltipBg, border: `1px solid ${chartColors.tooltipBorder}`, borderRadius: '8px' }} />
                  <Bar dataKey="value" name="Subcontractors" fill={chartColors.primary} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="no-data-message">No subcontractor data available.</p>
            )}
          </div>
        </Card>

        <Card title="Top Trades" description="Most common trades across your organization">
          <div className="analytics-chart-container">
            {tradeDistribution.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={tradeDistribution} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                  <XAxis type="number" stroke={chartColors.axis} fontSize={12} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" stroke={chartColors.axis} fontSize={12} width={110} />
                  <Tooltip contentStyle={{ background: chartColors.tooltipBg, border: `1px solid ${chartColors.tooltipBorder}`, borderRadius: '8px' }} />
                  <Bar dataKey="value" name="Subcontractors" fill={chartColors.secondary} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="no-data-message">No trade data available.</p>
            )}
          </div>
        </Card>

        <Card title="Compliance Rate Trend" description="Organization compliance percentage over time">
          <div className="analytics-chart-container">
            {complianceTrendChart.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={complianceTrendChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                  <XAxis dataKey="date" stroke={chartColors.axis} fontSize={12} />
                  <YAxis stroke={chartColors.axis} fontSize={12} domain={[0, 100]} />
                  <Tooltip contentStyle={{ background: chartColors.tooltipBg, border: `1px solid ${chartColors.tooltipBorder}`, borderRadius: '8px' }} />
                  <Bar dataKey="compliancePercentage" name="Compliance %" fill={chartColors.success} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="no-data-message">No compliance trend data available.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default SubcontractorAnalyticsDashboard;
