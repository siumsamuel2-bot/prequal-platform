import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AnalyticsHub from '../components/analytics/AnalyticsHub';

jest.mock('../api/client', () => ({
  analyticsApi: {
    getPilotEngagement: jest.fn().mockResolvedValue(null),
    getDailyActiveUsers: jest.fn().mockResolvedValue([]),
    getEvents: jest.fn().mockResolvedValue([]),
    getAnomalies: jest.fn().mockResolvedValue({ anomalies: [], total: 0 }),
    getWeeklyReport: jest.fn().mockResolvedValue(null),
    getFeatureAdoption: jest.fn().mockResolvedValue([]),
    getSystemHealth: jest.fn().mockResolvedValue([]),
  },
  complianceAnalyticsApi: {
    getSummary: jest.fn().mockResolvedValue(null),
    getTrends: jest.fn().mockResolvedValue([]),
  },
  complianceApi: {
    getStateCredentialsSummary: jest.fn().mockResolvedValue(null),
  },
  subcontractorApi: {
    getAll: jest.fn().mockResolvedValue([]),
  },
  analyticsTracker: {
    trackReportExport: jest.fn(),
  },
}));

const setRole = (role) => {
  window.localStorage.setItem(
    'auth_state',
    JSON.stringify({
      token: 'test-token',
      isAuthenticated: true,
      user: { id: 'u1', email: 'a@b.c', name: 'Test', role, is_active: true, teams: [] },
    }),
  );
  window.localStorage.setItem('access_token', 'test-token');
};

const renderHub = (initialEntry = '/analytics/pilot-engagement') =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/analytics/*" element={<AnalyticsHub />} />
      </Routes>
    </MemoryRouter>
  );

describe('AnalyticsHub', () => {
  beforeAll(() => {
    if (!global.ResizeObserver) {
      global.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      };
    }
  });

  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  afterEach(() => {
    document.documentElement.removeAttribute('data-theme');
  });

  test('renders the four dashboard tabs', () => {
    setRole('admin');
    renderHub();

    expect(screen.getByRole('tab', { name: /pilot engagement/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /compliance/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /subcontractors/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /system health/i })).toBeInTheDocument();
  });

  test('shows admin gate for non-admin users on admin-only tabs', async () => {
    setRole('member');
    renderHub('/analytics/pilot-engagement');

    await waitFor(() => {
      expect(screen.getByText('Admin access required')).toBeInTheDocument();
    });
    expect(
      screen.getByRole('link', { name: 'Open Compliance Analytics' }),
    ).toBeInTheDocument();
  });

  test('compliance tab is available to non-admin users', async () => {
    setRole('member');
    renderHub('/analytics/compliance');

    await waitFor(() => {
      expect(screen.getByTestId('compliance-analytics-dashboard')).toBeInTheDocument();
    });
  });

  test('navigates between tabs on click', async () => {
    setRole('admin');
    renderHub('/analytics/pilot-engagement');

    await waitFor(() => {
      expect(screen.getByTestId('pilot-engagement-dashboard')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: /compliance/i }));
    await waitFor(() => {
      expect(screen.getByTestId('compliance-analytics-dashboard')).toBeInTheDocument();
    });
  });

  test('supports arrow key tab navigation', async () => {
    setRole('admin');
    renderHub('/analytics/pilot-engagement');

    const pilotTab = screen.getByRole('tab', { name: /pilot engagement/i });
    pilotTab.focus();

    fireEvent.keyDown(pilotTab, { key: 'ArrowRight' });

    await waitFor(() => {
      expect(screen.getByTestId('compliance-analytics-dashboard')).toBeInTheDocument();
    });
    expect(screen.getByRole('tab', { name: /compliance/i })).toHaveFocus();
  });

  test('toggles dark theme and persists the choice', () => {
    setRole('admin');
    renderHub();

    const toggle = screen.getByRole('button', { name: /switch to dark theme/i });
    fireEvent.click(toggle);

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(window.localStorage.getItem('prequal_dashboard_theme')).toBe('dark');
    expect(screen.getByRole('button', { name: /switch to light theme/i })).toBeInTheDocument();
  });

  test('falls back to polling when no realtime WebSocket URL is configured', async () => {
    setRole('admin');
    renderHub();

    await waitFor(() => {
      expect(screen.getByLabelText(/auto-refreshing via periodic polling/i)).toBeInTheDocument();
    });
    expect(screen.getByText('Live (polling)')).toBeInTheDocument();
  });

  test('falls back to polling when the WebSocket connection cannot be established', async () => {
    const originalWebSocket = global.WebSocket;
    global.WebSocket = class {
      constructor() {
        throw new Error('WebSocket blocked');
      }
    };

    const originalEnv = process.env.VITE_ANALYTICS_WS_URL;
    process.env.VITE_ANALYTICS_WS_URL = 'ws://localhost:9999/analytics';

    try {
      setRole('admin');
      renderHub();

      await waitFor(() => {
        expect(screen.getByText('Live (polling)')).toBeInTheDocument();
      });
    } finally {
      global.WebSocket = originalWebSocket;
      if (originalEnv === undefined) delete process.env.VITE_ANALYTICS_WS_URL;
      else process.env.VITE_ANALYTICS_WS_URL = originalEnv;
    }
  });
});
