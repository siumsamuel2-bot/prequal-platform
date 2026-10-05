import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  analyticsApi,
  SystemHealthData,
  AnomalyRecord,
} from '../../api/client';
import { useDashboardData } from '../../hooks/useDashboardData';
import type { RealtimeConnectionState } from '../../hooks/useRealtimeConnection';
import { useDashboardTheme } from '../../hooks/useDashboardTheme';
import { exportRowsToCsv, exportPageToPdf } from '../../utils/exportUtils';
import { Card, Button, Select, Badge, Table, type TableColumn } from '../ui';
import LiveIndicator from './LiveIndicator';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

type HealthStatus = 'healthy' | 'warning' | 'critical';

const HEALTH_BADGE_VARIANT: Record<HealthStatus, 'success' | 'warning' | 'danger'> = {
  healthy: 'success',
  warning: 'warning',
  critical: 'danger',
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

const formatMetricValue = (value: number | null | undefined, unit?: string | null): string =>
  value === undefined || value === null
    ? '—'
    : `${Number(value).toFixed(Number.isInteger(value) ? 0 : 1)}${unit ?? ''}`;

const severityVariant = (severity: string): 'danger' | 'warning' | 'info' => {
  const normalized = severity.toLowerCase();
  if (normalized === 'high' || normalized === 'critical') return 'danger';
  if (normalized === 'medium' || normalized === 'warning') return 'warning';
  return 'info';
};

interface Props {
  realtime: RealtimeConnectionState;
}

const SystemHealthDashboard: React.FC<Props> = ({ realtime }) => {
  const { chartColors } = useDashboardTheme();
  const [hours, setHours] = useState('24');

  const realtimeLive = realtime.mode === 'websocket' && realtime.connected;

  const health = useDashboardData(
    useCallback(() => analyticsApi.getSystemHealth({ hours: Number(hours) }), [hours]),
    { refreshIntervalMs: 30000, isRealtimeLive: realtimeLive },
  );
  const anomalies = useDashboardData(
    useCallback(() => analyticsApi.getAnomalies(), []),
    { refreshIntervalMs: 60000, isRealtimeLive: realtimeLive },
  );
  const adoption = useDashboardData(
    useCallback(() => analyticsApi.getFeatureAdoption({ days: 30 }), []),
    { refreshIntervalMs: 60000, isRealtimeLive: realtimeLive },
  );
  const weekly = useDashboardData(
    useCallback(() => analyticsApi.getWeeklyReport(), []),
    { refreshIntervalMs: 300000, isRealtimeLive: realtimeLive },
  );

  const refetchAll = useCallback(() => {
    health.refetch();
    anomalies.refetch();
    adoption.refetch();
    weekly.refetch();
  }, [health, anomalies, adoption, weekly]);

  useEffect(() => {
    if (realtime.lastMessageAt) refetchAll();
  }, [realtime.lastMessageAt, refetchAll]);

  const services = health.data ?? [];
  const anomalyRows = anomalies.data?.anomalies ?? [];
  const weeklyReport = weekly.data;

  const overallStatus: HealthStatus = useMemo(() => {
    const statuses = services.map(getHealthStatus);
    if (statuses.includes('critical')) return 'critical';
    if (statuses.includes('warning')) return 'warning';
    return 'healthy';
  }, [services]);

  const adoptionChart = useMemo(
    () =>
      [...(adoption.data ?? [])]
        .sort((a, b) => b.total_events - a.total_events)
        .slice(0, 8)
        .map((feature) => ({
          name: feature.feature_name,
          totalEvents: feature.total_events,
          uniqueUsers: feature.unique_users,
        })),
    [adoption.data],
  );

  const handleExportCsv = () => {
    exportRowsToCsv(
      'system_health',
      `system-health-${new Date().toISOString().slice(0, 10)}`,
      ['service_name', 'metric_name', 'metric_unit', 'avg_value', 'min_value', 'max_value', 'p95_value', 'total_count'],
      services.map((service) => ({
        service_name: service.service_name,
        metric_name: service.metric_name,
        metric_unit: service.metric_unit ?? '',
        avg_value: service.avg_value,
        min_value: service.min_value,
        max_value: service.max_value,
        p95_value: service.p95_value,
        total_count: service.total_count,
      })),
    );
  };

  const serviceColumns: TableColumn<SystemHealthData & Record<string, unknown>>[] = [
    { key: 'service_name', header: 'Service' },
    { key: 'metric_name', header: 'Metric' },
    {
      key: 'avg_value',
      header: 'Average',
      render: (value, row) => formatMetricValue(value as number, (row as SystemHealthData).metric_unit),
    },
    {
      key: 'p95_value',
      header: 'p95',
      render: (value, row) => formatMetricValue(value as number, (row as SystemHealthData).metric_unit),
    },
    { key: 'total_count', header: 'Samples' },
    {
      key: 'status',
      header: 'Status',
      sortable: false,
      render: (_value, row) => {
        const status = getHealthStatus(row as SystemHealthData);
        return <Badge variant={HEALTH_BADGE_VARIANT[status]} dot>{status}</Badge>;
      },
    },
  ];

  const anomalyColumns: TableColumn<AnomalyRecord & Record<string, unknown>>[] = [
    { key: 'severity', header: 'Severity', render: (value) => <Badge variant={severityVariant(String(value))}>{String(value)}</Badge> },
    { key: 'type', header: 'Type' },
    { key: 'feature', header: 'Feature' },
    { key: 'message', header: 'Message' },
    {
      key: 'detected_at',
      header: 'Detected',
      render: (value) => new Date(String(value)).toLocaleString('en-US'),
    },
  ];

  return (
    <div className="analytics-page" data-testid="system-health-dashboard">
      <div className="analytics-toolbar">
        <div className="analytics-filters">
          <Select
            options={[
              { value: '24', label: 'Last 24 hours' },
              { value: '72', label: 'Last 72 hours' },
              { value: '168', label: 'Last 7 days' },
            ]}
            value={hours}
            onChange={setHours}
            label="Health window"
          />
          <span
            className={`overall-health overall-${overallStatus}`}
            role="status"
            aria-label={`Overall system status: ${overallStatus}`}
          >
            Overall: {overallStatus}
          </span>
        </div>
        <div className="analytics-actions">
          <LiveIndicator connection={realtime} />
          <Button size="sm" onClick={refetchAll} aria-label="Refresh system health data">↻ Refresh</Button>
          <Button size="sm" variant="secondary" onClick={handleExportCsv} aria-label="Export system health as CSV">⬇ CSV</Button>
          <Button size="sm" variant="secondary" onClick={() => exportPageToPdf('system_health')} aria-label="Print dashboard as PDF">🖨 PDF</Button>
        </div>
      </div>

      <div className="analytics-grid">
        <Card title="Service Health" description={`p95 and average metrics across services (${hours}h window)`}>
          <Table
            columns={serviceColumns}
            data={services as (SystemHealthData & Record<string, unknown>)[]}
            keyExtractor={(row) => `${row.service_name}-${row.metric_name}`}
            loading={health.loading && services.length === 0}
            emptyMessage="No system health metrics recorded in this window."
          />
          {health.error && <p className="analytics-error" role="alert">{health.error}</p>}
        </Card>

        <Card
          title={`Anomaly Detection (${anomalyRows.length})`}
          description="Flagged usage anomalies from the analytics service"
        >
          <Table
            columns={anomalyColumns}
            data={anomalyRows as (AnomalyRecord & Record<string, unknown>)[]}
            keyExtractor={(row) => `${row.type}-${row.feature}-${row.detected_at}`}
            loading={anomalies.loading && anomalyRows.length === 0}
            emptyMessage="No anomalies detected."
          />
        </Card>
      </div>

      <div className="analytics-grid">
        <Card title="Feature Adoption (Last 30 Days)" description="Events and unique users per feature">
          <div className="analytics-chart-container">
            {adoptionChart.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={adoptionChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                  <XAxis dataKey="name" stroke={chartColors.axis} fontSize={12} interval={0} angle={-20} textAnchor="end" height={60} />
                  <YAxis stroke={chartColors.axis} fontSize={12} />
                  <Tooltip contentStyle={{ background: chartColors.tooltipBg, border: `1px solid ${chartColors.tooltipBorder}`, borderRadius: '8px' }} />
                  <Legend />
                  <Bar dataKey="totalEvents" name="Total Events" fill={chartColors.primary} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="uniqueUsers" name="Unique Users" fill={chartColors.secondary} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="no-data-message">No feature adoption data available.</p>
            )}
          </div>
        </Card>

        <Card
          title="Weekly Report Highlights"
          description={weeklyReport ? `Generated ${new Date(weeklyReport.generated_at).toLocaleString('en-US')}` : undefined}
        >
          {weekly.loading && !weeklyReport ? (
            <p className="no-data-message">Loading weekly report…</p>
          ) : weeklyReport ? (
            <div className="weekly-report">
              <div className="weekly-stat-row">
                <span>Features tracked</span>
                <span className="weekly-stat-value">{weeklyReport.feature_adoption.length}</span>
              </div>
              <div className="weekly-stat-row">
                <span>Health metrics</span>
                <span className="weekly-stat-value">{weeklyReport.system_health.length}</span>
              </div>
              <div className="weekly-stat-row">
                <span>Alerts</span>
                <span className={`weekly-stat-value ${weeklyReport.alerts.length > 0 ? 'stat-warning' : 'stat-ok'}`}>
                  {weeklyReport.alerts.length}
                </span>
              </div>
              {weeklyReport.alerts.length > 0 && (
                <ul className="weekly-alert-list">
                  {weeklyReport.alerts.map((alert, index) => (
                    <li key={`${alert.type}-${alert.feature}-${index}`}>{alert.message}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <p className="no-data-message">No weekly report available.</p>
          )}
        </Card>
      </div>
    </div>
  );
};

export default SystemHealthDashboard;
