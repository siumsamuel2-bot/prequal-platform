import React from 'react';

export type MetricTrend = 'up' | 'down' | 'flat' | null;

export interface MetricCardProps {
  label: string;
  value: string;
  icon?: string;
  /** Decorative accent color; text uses theme-aware tokens for contrast. */
  accent?: string;
  trend?: MetricTrend;
  trendLabel?: string;
  hint?: string;
}

/**
 * Theme-aware KPI card used across the analytics dashboards (MID-592).
 * Colors come from CSS variables so the card passes contrast checks in
 * both light and dark themes (WCAG 2.1 AA).
 */
export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  icon,
  accent,
  trend,
  trendLabel,
  hint,
}) => {
  const trendIcon = trend === 'up' ? '▲' : trend === 'down' ? '▼' : null;
  const trendClass = trend === 'up' ? 'trend-up' : trend === 'down' ? 'trend-down' : '';

  return (
    <div className="analytics-metric-card" style={accent ? { borderTopColor: accent } : undefined}>
      <div className="analytics-metric-top">
        <span className="analytics-metric-label">{label}</span>
        {icon && (
          <span className="analytics-metric-icon" aria-hidden="true">
            {icon}
          </span>
        )}
      </div>
      <div className="analytics-metric-value">{value}</div>
      <div className="analytics-metric-footer">
        {trendIcon && (
          <span className={`analytics-metric-trend ${trendClass}`} aria-hidden="true">
            {trendIcon}
          </span>
        )}
        {trendLabel && (
          <span className="analytics-metric-trend-label">
            {trendIcon && <span className="sr-only">{trend === 'up' ? 'Increasing' : 'Decreasing'}: </span>}
            {trendLabel}
          </span>
        )}
        {hint && !trendLabel && <span className="analytics-metric-hint">{hint}</span>}
      </div>
    </div>
  );
};

export default MetricCard;
