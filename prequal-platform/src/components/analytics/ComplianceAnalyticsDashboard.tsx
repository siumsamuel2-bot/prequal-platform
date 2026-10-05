import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  complianceAnalyticsApi,
  complianceApi,
  ComplianceSummaryData,
  ComplianceTrendPoint,
  StateCredentialSummary,
} from '../../api/client';
import { useDashboardData } from '../../hooks/useDashboardData';
import type { RealtimeConnectionState } from '../../hooks/useRealtimeConnection';
import { useDashboardTheme } from '../../hooks/useDashboardTheme';
import { exportRowsToCsv, exportPageToPdf } from '../../utils/exportUtils';
import { Card, Button, Select } from '../ui';
import MetricCard from './MetricCard';
import LiveIndicator from './LiveIndicator';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  PieChart, Pie, Cell,
} from 'recharts';

const formatNumber = (value?: number | null): string =>
  value !== undefined && value !== null ? value.toLocaleString('en-US') : '—';

const formatPercent = (value?: number | null): string =>
  value !== undefined && value !== null ? `${Number(value).toFixed(1)}%` : '—';

const PIE_COLORS = ['#10b981', '#f59e0b', '#ef4444', '#3b82f6'];

interface Props {
  realtime: RealtimeConnectionState;
}

const ComplianceAnalyticsDashboard: React.FC<Props> = ({ realtime }) => {
  const { chartColors } = useDashboardTheme();
  const [days, setDays] = useState('30');

  const realtimeLive = realtime.mode === 'websocket' && realtime.connected;

  const summary = useDashboardData(
    useCallback(() => complianceAnalyticsApi.getSummary(), []),
    { refreshIntervalMs: 60000, isRealtimeLive: realtimeLive },
  );
  const trends = useDashboardData(
    useCallback(() => complianceAnalyticsApi.getTrends(Number(days)), [days]),
    { refreshIntervalMs: 60000, isRealtimeLive: realtimeLive },
  );
  const stateCreds = useDashboardData(
    useCallback(() => complianceApi.getStateCredentialsSummary(), []),
    { refreshIntervalMs: 120000, isRealtimeLive: realtimeLive },
  );

  const refetchAll = useCallback(() => {
    summary.refetch();
    trends.refetch();
    stateCreds.refetch();
  }, [summary, trends, stateCreds]);

  useEffect(() => {
    if (realtime.lastMessageAt) refetchAll();
  }, [realtime.lastMessageAt, refetchAll]);

  const summaryData: ComplianceSummaryData | null = summary.data;
  const trendRows: ComplianceTrendPoint[] = trends.data ?? [];
  const credSummary: StateCredentialSummary | null = stateCreds.data;

  const trendChart = useMemo(
    () =>
      trendRows.map((point) => ({
        date: point.date
          ? new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
          : '',
        validCertifications: point.valid_certifications,
        expiredCertifications: point.expired_certifications,
        compliancePercentage: point.compliance_percentage,
      })),
    [trendRows],
  );

  const certDistribution = useMemo(() => {
    const valid = credSummary?.active ?? summaryData?.valid_certifications ?? 0;
    const expiring = summaryData?.expiring_soon_30d ?? 0;
    const expired = credSummary?.expired ?? summaryData?.expired_certifications ?? 0;
    return [
      { name: 'Valid', value: valid },
      { name: 'Expiring (30d)', value: expiring },
      { name: 'Expired', value: expired },
    ].filter((entry) => entry.value > 0);
  }, [credSummary, summaryData]);

  const handleExportCsv = () => {
    exportRowsToCsv(
      'compliance_analytics',
      `compliance-analytics-${new Date().toISOString().slice(0, 10)}`,
      ['date', 'active_subcontractors', 'valid_certifications', 'expired_certifications', 'compliance_percentage'],
      trendRows.map((point) => ({
        date: point.date ?? '',
        active_subcontractors: point.active_subcontractors,
        valid_certifications: point.valid_certifications,
        expired_certifications: point.expired_certifications,
        compliance_percentage: point.compliance_percentage,
      })),
    );
  };

  return (
    <div className="analytics-page" data-testid="compliance-analytics-dashboard">
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
            label="Trend range"
          />
          <span className="scope-badge" title="Compliance data is scoped to your organization (MID-544/545/546/547)">
            Org-scoped
          </span>
        </div>
        <div className="analytics-actions">
          <LiveIndicator connection={realtime} />
          <Button size="sm" onClick={refetchAll} aria-label="Refresh compliance analytics">↻ Refresh</Button>
          <Button size="sm" variant="secondary" onClick={handleExportCsv} aria-label="Export compliance trends as CSV">⬇ CSV</Button>
          <Button size="sm" variant="secondary" onClick={() => exportPageToPdf('compliance_analytics')} aria-label="Print dashboard as PDF">🖨 PDF</Button>
        </div>
      </div>

      <div className="analytics-metric-grid">
        <MetricCard label="Compliance Rate" value={formatPercent(summaryData?.compliance_rate)} icon="🛡" accent={chartColors.success} hint="Valid vs required certifications" />
        <MetricCard label="Total Subcontractors" value={formatNumber(summaryData?.total_subcontractors)} icon="👷" accent={chartColors.primary} />
        <MetricCard label="Expiring (30d)" value={formatNumber(summaryData?.expiring_soon_30d)} icon="⏳" accent={chartColors.warning} hint="Renewals due this month" />
        <MetricCard label="Expiring (60d)" value={formatNumber(summaryData?.expiring_soon_60d)} icon="🗓" accent={chartColors.warning} />
        <MetricCard label="Expired Certifications" value={formatNumber(summaryData?.expired_certifications)} icon="⚠️" accent={chartColors.danger} />
        <MetricCard label="Valid Certifications" value={formatNumber(summaryData?.valid_certifications)} icon="✅" accent={chartColors.success} />
        <MetricCard label="Open Violations" value={formatNumber(summaryData?.open_violations)} icon="🚧" accent={chartColors.danger} />
        <MetricCard label="Pending Verification" value={formatNumber(summaryData?.pending_verification_certs)} icon="🔍" accent={chartColors.info} />
      </div>

      <div className="analytics-grid">
        <Card title="Certification Health Trends" description="Valid vs expired certifications and compliance percentage">
          <div className="analytics-chart-container">
            {trendChart.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={trendChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                  <XAxis dataKey="date" stroke={chartColors.axis} fontSize={12} />
                  <YAxis stroke={chartColors.axis} fontSize={12} />
                  <Tooltip contentStyle={{ background: chartColors.tooltipBg, border: `1px solid ${chartColors.tooltipBorder}`, borderRadius: '8px' }} />
                  <Legend />
                  <Area type="monotone" dataKey="validCertifications" name="Valid certifications" stroke={chartColors.success} fill={chartColors.success} fillOpacity={0.2} strokeWidth={2} />
                  <Area type="monotone" dataKey="expiredCertifications" name="Expired certifications" stroke={chartColors.danger} fill={chartColors.danger} fillOpacity={0.2} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="no-data-message">No compliance trend data available.</p>
            )}
          </div>
        </Card>

        <Card title="Certification Status Distribution" description="Current certification health mix">
          <div className="analytics-chart-container">
            {certDistribution.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={certDistribution} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={2} dataKey="value" nameKey="name">
                      {certDistribution.map((entry, index) => (
                        <Cell key={`cert-cell-${entry.name}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: chartColors.tooltipBg, border: `1px solid ${chartColors.tooltipBorder}`, borderRadius: '8px' }} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pie-legend">
                  {certDistribution.map((entry, index) => (
                    <span key={entry.name} className="legend-item">
                      <span className="legend-dot" style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }} aria-hidden="true" />
                      {entry.name}: {formatNumber(entry.value)}
                    </span>
                  ))}
                </div>
              </>
            ) : (
              <p className="no-data-message">No certification data available.</p>
            )}
          </div>
        </Card>
      </div>

      {summary.error && <p className="analytics-error" role="alert">{summary.error}</p>}
    </div>
  );
};

export default ComplianceAnalyticsDashboard;
