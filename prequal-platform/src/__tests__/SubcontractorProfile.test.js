import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import SubcontractorProfile from '../components/SubcontractorProfile';
import { ToastProvider } from '../components/ToastContext';
import { subcontractorApi, certificationApi, violationApi } from '../api/client';

const mockSubcontractor = {
  id: '1',
  company_name: 'ABC Construction Co.',
  email: 'john@abc.com',
  phone: '555-123-4567',
  status: 'active',
  contact_first_name: 'John',
  contact_last_name: 'Smith'
};

const mockCertifications = [
  {
    id: '1',
    subcontractor_id: '1',
    certification_type: 'OSHA 30',
    certification_number: 'OSHA-30-123',
    issue_date: '2026-01-15',
    expiration_date: '2026-12-31',
    status: 'valid'
  }
];

const mockViolations = [];

jest.mock('../api/client', () => ({
  credentialsApi: {
    upload: jest.fn()
  },
  subcontractorApi: {
    getById: jest.fn(),
    update: jest.fn(),
    create: jest.fn(),
    downloadReport: jest.fn()
  },
  certificationApi: {
    getAll: jest.fn()
  },
  violationApi: {
    getAll: jest.fn()
  }
}));

const renderProfile = (route = '/subcontractors/1') =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <Routes>
          <Route path="/subcontractors/:id" element={<SubcontractorProfile />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  );

describe('SubcontractorProfile', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    subcontractorApi.getById.mockResolvedValue(mockSubcontractor);
    subcontractorApi.update.mockResolvedValue(mockSubcontractor);
    certificationApi.getAll.mockResolvedValue(mockCertifications);
    violationApi.getAll.mockResolvedValue(mockViolations);
  });

  test('renders subcontractor profile with all sections', async () => {
    renderProfile();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'ABC Construction Co.' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument();
    expect(screen.getByText('Download PDF')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Details' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Certifications (1)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Violations (0)' })).toBeInTheDocument();
    expect(screen.getByText('Save Profile')).toBeInTheDocument();

    expect(subcontractorApi.getById).toHaveBeenCalledWith('1');
  });

  test('displays company information from API', async () => {
    renderProfile();

    await waitFor(() => {
      expect(screen.getByDisplayValue('ABC Construction Co.')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('john@abc.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('555-123-4567')).toBeInTheDocument();
    expect(screen.getByDisplayValue('John')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Smith')).toBeInTheDocument();
  });

  test('shows certifications table when the certifications tab is selected', async () => {
    renderProfile();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'ABC Construction Co.' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Certifications (1)' }));

    expect(await screen.findByText('OSHA-30-123')).toBeInTheDocument();
    expect(screen.getByText('Issue Date')).toBeInTheDocument();
    expect(screen.getByText('Expiration')).toBeInTheDocument();
    expect(screen.getByText('valid')).toBeInTheDocument();
  });

  test('renders new subcontractor form for the new route', async () => {
    renderProfile('/subcontractors/new');

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Add New Subcontractor' })).toBeInTheDocument();
    });
    expect(screen.getByText('Create Subcontractor')).toBeInTheDocument();
    expect(screen.getByLabelText('Company Name *')).toBeInTheDocument();
  });
});
