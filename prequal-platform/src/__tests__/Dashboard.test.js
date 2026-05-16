import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import Dashboard from '../components/Dashboard';
import SubcontractorProfile from '../components/SubcontractorProfile';
import CertificationAlerts from '../components/CertificationAlerts';
import CredentialUpload from '../components/CredentialUpload';

const mockContractors = [
  {
    id: '1',
    company_name: 'ABC Construction Co.',
    contact_name: 'John Smith',
    email: 'john@abc.com',
    phone: '555-123-4567',
    address: '123 Main St'
  }
];

const mockComplianceStatus = {
  overall_status: 'COMPLIANT',
  compliance_score: 85,
  last_updated: '2026-05-11'
};

const mockCertifications = [
  {
    id: '1',
    certification_type: 'OSHA 30',
    expiration_date: '2026-12-31',
    status: 'valid'
  }
];

const mockViolations = [];

const mockAlerts = [
  {
    id: 1,
    type: 'warning',
    message: 'Certification expiring in 30 days'
  },
  {
    id: 2,
    type: 'info',
    message: 'Documentation requires verification'
  }
];

jest.mock('../api/client', () => ({
  contractorApi: {
    getAll: jest.fn(() => Promise.resolve(mockContractors)),
    getCertifications: jest.fn(() => Promise.resolve(mockCertifications)),
    getViolations: jest.fn(() => Promise.resolve(mockViolations))
  },
  complianceApi: {
    getStatus: jest.fn(() => Promise.resolve(mockComplianceStatus)),
    getAlerts: jest.fn(() => Promise.resolve(mockAlerts))
  },
  dashboardApi: {
    getSummary: jest.fn(() => Promise.resolve({
      total_subcontractors: 10,
      active_subcontractors: 8,
      compliance_rate: 80,
      total_projects: 5,
      active_projects: 3,
      expiring_this_month: 2,
      open_violations: 1,
      recent_alerts: mockAlerts
    }))
  }
}));

describe('Dashboard Components', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders dashboard with all components', async () => {
    render(<Dashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('Subcontractor Compliance Dashboard')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('SUBCONTRACTOR COMPLIANCE PROFILE')).toBeInTheDocument();
    });
    expect(screen.getByText('Certification Alerts')).toBeInTheDocument();
    expect(screen.getByText('Credential Upload Portal')).toBeInTheDocument();
  });

  test('renders subcontractor profile with updated structure', async () => {
    render(<SubcontractorProfile />);
    
    await waitFor(() => {
      expect(screen.getByText('SUBCONTRACTOR COMPLIANCE PROFILE')).toBeInTheDocument();
    });
    expect(screen.getByText('COMPANY INFORMATION')).toBeInTheDocument();
    expect(screen.getByText('PRIMARY CONTACT')).toBeInTheDocument();
    expect(screen.getByText('COMPLIANCE STATUS')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByLabelText('Company Name:')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('DBA Name:')).toBeInTheDocument();
    expect(screen.getByLabelText('Company Address:')).toBeInTheDocument();
    expect(screen.getByLabelText('Phone Number:')).toBeInTheDocument();
    expect(screen.getByLabelText('Website:')).toBeInTheDocument();
    expect(screen.getByLabelText('Contact Name:')).toBeInTheDocument();
    expect(screen.getByLabelText('Contact Title:')).toBeInTheDocument();
    expect(screen.getByLabelText('Contact Email:')).toBeInTheDocument();
    expect(screen.getByLabelText('Contact Phone:')).toBeInTheDocument();
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
    expect(screen.getByLabelText('Upload Certification Documents:')).toBeInTheDocument();
    expect(screen.getByLabelText('Document Type:')).toBeInTheDocument();
    expect(screen.getByText('Submit Documents')).toBeInTheDocument();
  });
});