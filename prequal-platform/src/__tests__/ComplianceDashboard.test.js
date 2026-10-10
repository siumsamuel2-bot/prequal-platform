import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ComplianceDashboard from '../components/ComplianceDashboard';
import { ToastProvider } from '../components/ToastContext';
import { ToastContainer } from '../components/ToastContainer';
import {
  complianceApi,
  complianceAnalyticsApi,
  projectApi,
  violationApi,
  certificationApi,
  ApiError,
} from '../api/client';

jest.mock('../api/client', () => {
  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
    }
  }
  return {
    ApiError,
    apiClient: {
      post: jest.fn(),
    },
    complianceApi: {
      getStatus: jest.fn(),
      getAlerts: jest.fn(),
      getStateCredentials: jest.fn(),
      getStateCredentialsSummary: jest.fn(),
    },
    complianceAnalyticsApi: {
      getTrends: jest.fn(),
      getSummary: jest.fn(),
    },
    projectApi: {
      getAll: jest.fn(),
    },
    violationApi: {
      getAll: jest.fn(),
    },
    certificationApi: {
      getAll: jest.fn(),
    },
  };
});

jest.mock('../components/QuickAddSubcontractorModal', () => ({
  QuickAddSubcontractorModal: () => null,
}));

const mockComplianceData = [
  {
    subcontractor_id: 'sub-1',
    company_name: 'BuildRight GC',
    state: 'TX',
    compliance_score: 85,
    status: 'COMPLIANT',
    active_certifications: 3,
    expiring_certifications: 0,
    expired_certifications: 0,
    open_violations: 0,
    resolved_violations: 1,
  },
  {
    subcontractor_id: 'sub-2',
    company_name: 'Apex Contracting',
    state: 'CA',
    compliance_score: 45,
    status: 'NON_COMPLIANT',
    active_certifications: 1,
    expiring_certifications: 1,
    expired_certifications: 1,
    open_violations: 2,
    resolved_violations: 0,
  },
];

const mockStateCredSummary = {
  total: 10,
  active: 7,
  expiring_soon: 2,
  expired: 1,
  unmatched: 0,
};

const adminAuthState = {
  user: {
    id: 'user-1',
    email: 'admin@example.com',
    name: 'Admin User',
    role: 'admin',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    teams: [],
  },
  token: 'test-token',
  isAuthenticated: true,
};

const renderDashboard = () =>
  render(
    <ToastProvider>
      <ComplianceDashboard />
      <ToastContainer />
    </ToastProvider>
  );

describe('ComplianceDashboard access states (MID-657)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.removeItem('auth_state');
    complianceApi.getStatus.mockResolvedValue(mockComplianceData);
    complianceApi.getStateCredentialsSummary.mockResolvedValue(mockStateCredSummary);
    complianceAnalyticsApi.getTrends.mockResolvedValue([]);
    complianceAnalyticsApi.getSummary.mockResolvedValue({
      total_subcontractors: 2,
      compliant_subcontractors: 1,
      compliance_rate: 50,
      expiring_soon_30d: 1,
      open_violations: 2,
      valid_certifications: 4,
      expired_certifications: 1,
      pending_verification_certs: 0,
    });
    projectApi.getAll.mockResolvedValue([]);
  });

  afterEach(() => {
    localStorage.removeItem('auth_state');
    localStorage.removeItem('access_token');
  });

  test('shows a calm no-access state on 403 for non-admins with no resolvable team', async () => {
    complianceApi.getStatus.mockRejectedValue(
      new ApiError('Tenant scope could not be resolved for this account', 403)
    );

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("You don't have access to this data")).toBeInTheDocument();
    });
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByText('Compliance Table')).not.toBeInTheDocument();
    expect(screen.queryByText('BuildRight GC')).not.toBeInTheDocument();
    expect(screen.queryByText('Failed to load compliance data')).not.toBeInTheDocument();
    expect(screen.queryByText('Analytics')).not.toBeInTheDocument();
  });

  test('shows a no-data-for-team state when a non-admin gets empty results', async () => {
    complianceApi.getStatus.mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('No data for your team')).toBeInTheDocument();
    });
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByText('No subcontractors match your filters')).not.toBeInTheDocument();
  });

  test('hides the admin-only Analytics tab for non-admins with data', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('BuildRight GC')).toBeInTheDocument();
    });
    expect(screen.getByText('Compliance Table')).toBeInTheDocument();
    expect(screen.getByText('State Level')).toBeInTheDocument();
    expect(screen.queryByText('Analytics')).not.toBeInTheDocument();
    expect(complianceAnalyticsApi.getTrends).not.toHaveBeenCalled();
    expect(complianceAnalyticsApi.getSummary).not.toHaveBeenCalled();
  });

  test('shows the Analytics tab for admins', async () => {
    localStorage.setItem('auth_state', JSON.stringify(adminAuthState));

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('BuildRight GC')).toBeInTheDocument();
    });
    expect(screen.getByText('Analytics')).toBeInTheDocument();
    expect(screen.queryByText("You don't have access to this data")).not.toBeInTheDocument();
  });

  test('keeps the error toast for genuine network failures', async () => {
    complianceApi.getStatus.mockRejectedValue(new Error('Network error'));

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
    expect(screen.queryByText("You don't have access to this data")).not.toBeInTheDocument();
  });
});
