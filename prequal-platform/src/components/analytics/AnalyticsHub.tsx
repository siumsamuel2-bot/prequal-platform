import React, { useCallback, useMemo, useRef } from 'react';
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import './AnalyticsPages.css';
import { useRealtimeConnection } from '../../hooks/useRealtimeConnection';
import { DashboardThemeProvider, useDashboardTheme } from '../../hooks/useDashboardTheme';
import { isAdmin } from '../../utils/auth';
import { Alert, Button } from '../ui';
import PilotEngagementDashboard from './PilotEngagementDashboard';
import ComplianceAnalyticsDashboard from './ComplianceAnalyticsDashboard';
import SubcontractorAnalyticsDashboard from './SubcontractorAnalyticsDashboard';
import SystemHealthDashboard from './SystemHealthDashboard';

const ANALYTICS_WS_URL =
  (typeof process !== 'undefined' && process.env && process.env.VITE_ANALYTICS_WS_URL) || '';

type TabKey = 'pilot-engagement' | 'compliance' | 'subcontractors' | 'system-health';

const TABS: Array<{ key: TabKey; label: string; adminOnly: boolean }> = [
  { key: 'pilot-engagement', label: 'Pilot Engagement', adminOnly: true },
  { key: 'compliance', label: 'Compliance', adminOnly: false },
  { key: 'subcontractors', label: 'Subcontractors', adminOnly: false },
  { key: 'system-health', label: 'System Health', adminOnly: true },
];

const AdminGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (isAdmin()) return <>{children}</>;
  return (
    <Alert variant="warning" title="Admin access required">
      <p>
        This dashboard uses platform-wide analytics endpoints that are restricted to
        administrators. Compliance and subcontractor analytics remain available for
        your organization.
      </p>
      <p className="admin-gate-links">
        <Link to="/analytics/compliance">Open Compliance Analytics</Link>
        <Link to="/analytics/subcontractors">Open Subcontractor Analytics</Link>
      </p>
    </Alert>
  );
};

const ThemeToggle: React.FC = () => {
  const { theme, toggleTheme } = useDashboardTheme();
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
      aria-pressed={theme === 'dark'}
      className="theme-toggle"
    >
      {theme === 'light' ? '🌙 Dark' : '☀️ Light'}
    </Button>
  );
};

const AnalyticsHubContent: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const realtime = useRealtimeConnection({ url: ANALYTICS_WS_URL });

  const activeTab = useMemo<TabKey>(() => {
    const match = TABS.find((tab) => location.pathname.includes(`/analytics/${tab.key}`));
    return match?.key ?? 'pilot-engagement';
  }, [location.pathname]);

  const activateTab = useCallback(
    (key: TabKey) => navigate(`/analytics/${key}`),
    [navigate],
  );

  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent, index: number) => {
      let nextIndex: number | null = null;
      if (event.key === 'ArrowRight') nextIndex = (index + 1) % TABS.length;
      if (event.key === 'ArrowLeft') nextIndex = (index - 1 + TABS.length) % TABS.length;
      if (event.key === 'Home') nextIndex = 0;
      if (event.key === 'End') nextIndex = TABS.length - 1;
      if (nextIndex === null) return;
      event.preventDefault();
      const nextTab = TABS[nextIndex];
      const nextRef = tabRefs.current[nextIndex];
      nextRef?.focus();
      activateTab(nextTab.key);
    },
    [activateTab],
  );

  return (
    <div className="analytics-hub" data-testid="analytics-hub">
      <header className="analytics-header">
        <div>
          <h1>Analytics</h1>
          <p className="analytics-subtitle">
            Pilot engagement, compliance, subcontractor and system health dashboards powered
            by the analytics service
          </p>
        </div>
        <div className="analytics-header-actions">
          <ThemeToggle />
          <Link className="action-btn" to="/analytics-dashboard">
            Legacy dashboard
          </Link>
        </div>
      </header>

      <div className="analytics-tabs" role="tablist" aria-label="Analytics dashboards">
        {TABS.map((tab, index) => (
          <button
            key={tab.key}
            ref={(node) => {
              tabRefs.current[index] = node;
            }}
            role="tab"
            id={`analytics-tab-${tab.key}`}
            aria-selected={activeTab === tab.key}
            aria-controls={`analytics-panel-${tab.key}`}
            tabIndex={activeTab === tab.key ? 0 : -1}
            className={`analytics-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => activateTab(tab.key)}
            onKeyDown={(event) => handleTabKeyDown(event, index)}
          >
            {tab.label}
            {tab.adminOnly && (
              <span className="admin-badge" title="Admin only">
                admin
              </span>
            )}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`analytics-panel-${activeTab}`}
        aria-labelledby={`analytics-tab-${activeTab}`}
        tabIndex={-1}
        className="analytics-panel"
      >
        <Routes>
          <Route index element={<Navigate to="/analytics/pilot-engagement" replace />} />
          <Route
            path="pilot-engagement"
            element={
              <AdminGate>
                <PilotEngagementDashboard realtime={realtime} />
              </AdminGate>
            }
          />
          <Route path="compliance" element={<ComplianceAnalyticsDashboard realtime={realtime} />} />
          <Route path="subcontractors" element={<SubcontractorAnalyticsDashboard realtime={realtime} />} />
          <Route
            path="system-health"
            element={
              <AdminGate>
                <SystemHealthDashboard realtime={realtime} />
              </AdminGate>
            }
          />
          <Route path="*" element={<Navigate to="/analytics/pilot-engagement" replace />} />
        </Routes>
      </div>
    </div>
  );
};

const AnalyticsHub: React.FC = () => (
  <DashboardThemeProvider>
    <AnalyticsHubContent />
  </DashboardThemeProvider>
);

export default AnalyticsHub;
