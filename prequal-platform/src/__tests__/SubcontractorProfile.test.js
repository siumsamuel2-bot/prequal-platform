import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SubcontractorProfile from '../components/SubcontractorProfile';

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

jest.mock('../api/client', () => ({
  contractorApi: {
    getAll: jest.fn(() => Promise.resolve(mockContractors)),
    getCertifications: jest.fn(() => Promise.resolve(mockCertifications)),
    getViolations: jest.fn(() => Promise.resolve(mockViolations))
  },
  complianceApi: {
    getStatus: jest.fn(() => Promise.resolve(mockComplianceStatus)),
    getAlerts: jest.fn(() => Promise.resolve([]))
  }
}));

describe('SubcontractorProfile', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders subcontractor profile with all sections', async () => {
    render(<SubcontractorProfile />);
    
    await waitFor(() => {
      expect(screen.getByText('SUBCONTRACTOR COMPLIANCE PROFILE')).toBeInTheDocument();
    });
    expect(screen.getByText('COMPANY INFORMATION')).toBeInTheDocument();
    expect(screen.getByText('PRIMARY CONTACT')).toBeInTheDocument();
    expect(screen.getByText('COMPLIANCE STATUS')).toBeInTheDocument();
  });

  test('displays company information from API', async () => {
    render(<SubcontractorProfile />);
    
    await waitFor(() => {
      expect(screen.getByDisplayValue('ABC Construction Co.')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('john@abc.com')).toBeInTheDocument();
  });
});