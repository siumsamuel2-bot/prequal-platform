import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import AnalyticsDashboard from '../components/AnalyticsDashboard';
import { ToastProvider } from '../components/ToastContext';
import { analyticsApi, billingApi } from '../api/client';

const mockEngagement = {
  total_organizations: 12,
  active_organizations_30d: 8,
  total_users: 142,
  active_users_30d: 95,
  avg_events_per_org: 240.5,
  onboarding_completion_rate: 66.7,
  feature_adoption_by_org: {},
  recently_active_orgs: [
    { organization_id: 1, organization_name: 'BuildRight GC', last_activity: '2026-09-28T10:00:00Z' },
    { organization_id: 2, organization_name: 'Apex Contracting', last_activity: '2026-09-27T08:30:00Z' },
  ],
  engagement_trends: [
    { date: '2026-09-28', active_organizations: 6, total_events: 120 },
    { date: '2026-09-29', active_organizations: 8, total_events: 180 },
  ],
};

const mockFeatureAdoption = [
  {
    feature_name: 'dashboard',
    total_events: 320,
    unique_users: 45,
    view_count: 300,
    action_count: 15,
    export_count: 5,
  },
  {
    feature_name: 'subcontractor_list',
    total_events: 210,
    unique_users: 30,
    view_count: 180,
    action_count: 20,
    export_count: 10,
  },
];

const mockSystemHealth = [
  {
    service_name: 'prequal-api',
    metric_name: 'response_time_ms',
    metric_unit: 'ms',
    avg_value: 120,
    min_value: 40,
    max_value: 900,
    p95_value: 250,
    total_count: 1000,
  },
];

const mockPerformance = {
  requests_per_second: 12.5,
  error_rate_percent: 0.2,
  avg_response_time_ms: 145.2,
  p50_response_time_ms: 120,
  p95_response_time_ms: 250,
  p99_response_time_ms: 375,
  active_db_connections: 8,
  max_db_connections: 20,
  active_requests: 3,
  rate_limit_hits: 2,
};

const mockSubscription = {
  plan: 'pro',
  status: 'active',
  current_period_end: '2026-10-15',
  subcontractor_limit: 100,
  subcontractor_count: 80,
  can_add_more: true,
};

const mockPlans = [
  { plan: 'starter', name: 'Starter', price: '$99/month', limit: 25, features: [] },
  { plan: 'pro', name: 'Pro', price: '$249/month', limit: 100, features: [] },
  { plan: 'enterprise', name: 'Enterprise', price: '$499/month', limit: 500, features: [] },
];

jest.mock('../api/client', () => ({
  analyticsApi: {
    getPilotEngagement: jest.fn(),
    getFeatureAdoption: jest.fn(),
    getSystemHealth: jest.fn(),
    getPerformanceMetrics: jest.fn(),
  },
  billingApi: {
    getSubscription: jest.fn(),
    getPlans: jest.fn(),
  },
}));

const renderDashboard = () =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <AnalyticsDashboard />
      </ToastProvider>
    </MemoryRouter>
  );

describe('AnalyticsDashboard', () => {
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
    jest.clearAllMocks();
    analyticsApi.getPilotEngagement.mockResolvedValue(mockEngagement);
    analyticsApi.getFeatureAdoption.mockResolvedValue(mockFeatureAdoption);
    analyticsApi.getSystemHealth.mockResolvedValue(mockSystemHealth);
    analyticsApi.getPerformanceMetrics.mockResolvedValue(mockPerformance);
    billingApi.getSubscription.mockResolvedValue(mockSubscription);
    billingApi.getPlans.mockResolvedValue(mockPlans);
  });

  test('renders KPI cards with data from all API endpoints', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('142')).toBeInTheDocument();
    });
    expect(screen.getByText('Total Users')).toBeInTheDocument();
    expect(screen.getByText('95')).toBeInTheDocument();
    expect(screen.getByText('Active Users (30d)')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('Total Organizations')).toBeInTheDocument();
    expect(screen.getByText('Active Organizations (30d)')).toBeInTheDocument();
    expect(screen.getByText('66.7%')).toBeInTheDocument();
    expect(screen.getByText('Onboarding Completion')).toBeInTheDocument();
    expect(screen.getByText('Pro ($249/month)')).toBeInTheDocument();
    expect(screen.getByText('Current Plan')).toBeInTheDocument();
    expect(screen.getAllByText('80%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Seat Utilization').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0.2%').length).toBeGreaterThan(0);
    expect(screen.getByText('API Error Rate')).toBeInTheDocument();
    expect(screen.getByText('145ms')).toBeInTheDocument();
    expect(screen.getByText('Avg Response Time')).toBeInTheDocument();
  });

  test('renders chart sections and system health details', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('User Growth & Engagement Trends')).toBeInTheDocument();
    });
    expect(screen.getByText('Feature Adoption (Last 30 Days)')).toBeInTheDocument();
    expect(screen.getByText('Revenue & Subscription')).toBeInTheDocument();
    expect(screen.getByText('System Health by Service')).toBeInTheDocument();
    expect(screen.getByText('Performance Summary')).toBeInTheDocument();
    expect(screen.getByText('Recently Active Organizations')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('BuildRight GC')).toBeInTheDocument();
    });
    expect(screen.getByText('Apex Contracting')).toBeInTheDocument();
    expect(screen.getByText('80/100')).toBeInTheDocument();
  });

  test('shows empty state message when feature adoption has no data', async () => {
    analyticsApi.getFeatureAdoption.mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('No feature adoption data available.')).toBeInTheDocument();
    });
  });

  test('renders remaining sections when user growth endpoint fails', async () => {
    analyticsApi.getPilotEngagement.mockRejectedValue(new Error('Network error'));

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Pro ($249/month)')).toBeInTheDocument();
    });
    expect(screen.getByText('Revenue & Subscription')).toBeInTheDocument();
    expect(screen.getByText('System Health by Service')).toBeInTheDocument();
    expect(screen.getByText('Total Users')).toBeInTheDocument();
  });

  test('calls all analytics and billing API endpoints on mount', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(analyticsApi.getPilotEngagement).toHaveBeenCalledWith(30);
    });
    expect(analyticsApi.getFeatureAdoption).toHaveBeenCalledWith({ days: 30 });
    expect(analyticsApi.getSystemHealth).toHaveBeenCalled();
    expect(analyticsApi.getPerformanceMetrics).toHaveBeenCalled();
    expect(billingApi.getSubscription).toHaveBeenCalled();
    expect(billingApi.getPlans).toHaveBeenCalled();
  });

  test('renders revenue distribution pie chart with plan legend', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Starter')).toBeInTheDocument();
    });
    expect(screen.getByText('Pro (current)')).toBeInTheDocument();
    expect(screen.getByText('Enterprise')).toBeInTheDocument();
    expect(screen.queryByText('No revenue distribution data available.')).not.toBeInTheDocument();
  });

  test('shows empty state for revenue distribution when plans fail to load', async () => {
    billingApi.getPlans.mockRejectedValue(new Error('Network error'));

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('No revenue distribution data available.')).toBeInTheDocument();
    });
  });

  test('renders system health status indicators for healthy services', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getAllByText('Healthy')).toHaveLength(2);
    });
    expect(screen.getByLabelText('Overall system status: Healthy')).toBeInTheDocument();
    expect(
      screen.getByLabelText('prequal-api — response_time_ms health status: Healthy')
    ).toBeInTheDocument();
  });

  test('flags critical system health status when p95 exceeds threshold', async () => {
    analyticsApi.getSystemHealth.mockResolvedValue([
      { ...mockSystemHealth[0], p95_value: 1500 },
    ]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByLabelText('Overall system status: Critical')).toBeInTheDocument();
    });
    expect(
      screen.getByLabelText('prequal-api — response_time_ms health status: Critical')
    ).toBeInTheDocument();
  });

  test('flags warning system health status when p95 is elevated', async () => {
    analyticsApi.getSystemHealth.mockResolvedValue([
      { ...mockSystemHealth[0], p95_value: 600 },
    ]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByLabelText('Overall system status: Warning')).toBeInTheDocument();
    });
    expect(
      screen.getByLabelText('prequal-api — response_time_ms health status: Warning')
    ).toBeInTheDocument();
  });
});
