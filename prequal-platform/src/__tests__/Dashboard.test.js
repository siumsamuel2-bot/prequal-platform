import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import Dashboard from '../components/Dashboard';
import SubcontractorProfile from '../components/SubcontractorProfile';
import CertificationAlerts from '../components/CertificationAlerts';
import CredentialUpload from '../components/CredentialUpload';

describe('Dashboard Components', () => {
  test('renders dashboard with all components', () => {
    render(<Dashboard />);
    
    expect(screen.getByText('Subcontractor Compliance Dashboard')).toBeInTheDocument();
    expect(screen.getByText('SUBCONTRACTOR COMPLIANCE PROFILE')).toBeInTheDocument();
    expect(screen.getByText('Certification Alerts')).toBeInTheDocument();
    expect(screen.getByText('Credential Upload Portal')).toBeInTheDocument();
  });

  test('renders subcontractor profile with updated structure', () => {
    render(<SubcontractorProfile />);
    
    expect(screen.getByText('SUBCONTRACTOR COMPLIANCE PROFILE')).toBeInTheDocument();
    expect(screen.getByText('COMPANY INFORMATION')).toBeInTheDocument();
    expect(screen.getByText('PRIMARY CONTACT')).toBeInTheDocument();
    expect(screen.getByText('COMPLIANCE STATUS')).toBeInTheDocument();
    
    // Check form fields
    expect(screen.getByLabelText('Company Name:')).toBeInTheDocument();
    expect(screen.getByLabelText('DBA Name:')).toBeInTheDocument();
    expect(screen.getByLabelText('Company Address:')).toBeInTheDocument();
    expect(screen.getByLabelText('Phone Number:')).toBeInTheDocument();
    expect(screen.getByLabelText('Website:')).toBeInTheDocument();
    expect(screen.getByLabelText('Contact Name:')).toBeInTheDocument();
    expect(screen.getByLabelText('Contact Title:')).toBeInTheDocument();
    expect(screen.getByLabelText('Contact Email:')).toBeInTheDocument();
    expect(screen.getByLabelText('Contact Phone:')).toBeInTheDocument();
  });

  test('renders certification alerts', () => {
    render(<CertificationAlerts />);
    
    expect(screen.getByText('Certification Alerts')).toBeInTheDocument();
    expect(screen.getByText('Certification expiring in 30 days')).toBeInTheDocument();
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