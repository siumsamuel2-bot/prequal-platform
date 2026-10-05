import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import Dashboard from '../components/Dashboard';
import CertificationAlerts from '../components/CertificationAlerts';
import CredentialUpload from '../components/CredentialUpload';
import { ToastProvider } from '../components/ToastContext';
import { dashboardApi, complianceApi, organizationApi } from '../api/client';

const mockAlerts = [
  { id: 1, type: 'warning', message: 'Certification expiring in 30 days' },
  { id: 2, type: 'info', message: 'Documentation requires verification' }
];

const mockSummary = {
  total_subcontractors: 10,
  active_subcontractors: 8,
  compliance_rate: 80,
  total_projects: 5,
  active_projects: 3,
  expiring_this_month: 2,
  open_violations: 1,
  recent_alerts: mockAlerts
};

jest.mock('../api/client', () => ({
  apiClient: { post: jest.fn() },
  organizationApi: {
    getOnboardingStatus: jest.fn(() => Promise.resolve({ step: 0 }))
  },
  dashboardApi: {
    getSummary: jest.fn()
  },
  complianceApi: {
    getAlerts: jest.fn()
  }
}));

const renderDashboard = () =>
  render(
    <ToastProvider>
      <Dashboard />
    </ToastProvider>
  );

describe('Dashboard Components', () => {
  beforeAll(() => {
    if (!global.ResizeObserver) {
      global.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      };
    }
    global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve([]) }));
  });

  beforeEach(() => {
    jest.clearAllMocks();
    dashboardApi.getSummary.mockResolvedValue(mockSummary);
    complianceApi.getAlerts.mockResolvedValue(mockAlerts);
    global.fetch.mockResolvedValue({ json: () => Promise.resolve([]) });
  });

  test('renders dashboard with summary metrics and alerts', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    });
    expect(screen.getByText('Total Subcontractors')).toBeInTheDocument();
    expect(screen.getByText('Active Subcontractors')).toBeInTheDocument();
    expect(screen.getByText('Compliance Rate')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
    expect(screen.getByText('Expiring This Month')).toBeInTheDocument();
    expect(screen.getAllByText('Open Violations').length).toBeGreaterThan(0);
    expect(screen.getByText('Active Projects')).toBeInTheDocument();

    expect(screen.getByText('Compliance Trends (30 Days)')).toBeInTheDocument();
    expect(screen.getByText('Recent Alerts')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('Certification expiring in 30 days')).toBeInTheDocument();
    });
    expect(screen.getByText('Documentation requires verification')).toBeInTheDocument();

    expect(screen.getByText('Export Reports')).toBeInTheDocument();
    expect(screen.getByText('Download CSV')).toBeInTheDocument();
    expect(screen.getByText('Quick Actions')).toBeInTheDocument();
  });

  test('renders certification alerts', async () => {
    render(<CertificationAlerts />);

    await waitFor(() => {
      expect(screen.getByText('Certification Alerts')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('Certification expiring in 30 days')).toBeInTheDocument();
    });
    expect(screen.getByText('Documentation requires verification')).toBeInTheDocument();
  });

  test('renders credential upload form', () => {
    render(<CredentialUpload />);

    expect(screen.getByText('Credential Upload Portal')).toBeInTheDocument();
    expect(screen.getByText('Drag and drop files here or')).toBeInTheDocument();
    expect(screen.getByText('click to browse')).toBeInTheDocument();
    expect(screen.getByText('Accepted file types: PNG, JPG, PDF, DOC, DOCX (Max 10MB)')).toBeInTheDocument();
    expect(screen.getByLabelText('Document Type:')).toBeInTheDocument();
    expect(screen.getByText('Submit Documents')).toBeInTheDocument();
  });
});
