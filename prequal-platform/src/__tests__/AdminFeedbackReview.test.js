import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import AdminFeedbackReview from '../components/AdminFeedbackReview';
import { ToastProvider } from '../components/ToastContext';
import { ToastContainer } from '../components/ToastContainer';
import { feedbackApi, ApiError } from '../api/client';

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
    feedbackApi: {
      submit: jest.fn(),
      list: jest.fn(),
      update: jest.fn(),
    },
  };
});

const mockSubmissions = [
  {
    id: 'fb-1',
    org_id: 'org-1',
    user_id: 'user-2',
    type: 'rating',
    surface: 'analytics_dashboard',
    page_url: '/analytics-dashboard',
    rating: 1,
    message: 'Charts are too slow',
    status: 'new',
    created_at: '2026-10-09T12:00:00Z',
  },
  {
    id: 'fb-2',
    org_id: 'org-1',
    user_id: null,
    type: 'support',
    surface: 'contact_page',
    page_url: '/support',
    rating: null,
    message: 'Export is failing',
    status: 'triaged',
    created_at: '2026-10-08T09:00:00Z',
  },
];

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

const renderView = () =>
  render(
    <ToastProvider>
      <AdminFeedbackReview />
      <ToastContainer />
    </ToastProvider>
  );

describe('AdminFeedbackReview', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.setItem('auth_state', JSON.stringify(adminAuthState));
    feedbackApi.list.mockResolvedValue({ items: mockSubmissions, total: mockSubmissions.length });
    feedbackApi.update.mockImplementation((id, data) =>
      Promise.resolve({ ...mockSubmissions.find((s) => s.id === id), ...data })
    );
  });

  afterEach(() => {
    localStorage.removeItem('auth_state');
    localStorage.removeItem('access_token');
  });

  test('shows the no-access state and does not fetch for non-admins', async () => {
    localStorage.removeItem('auth_state');
    renderView();

    await waitFor(() => {
      expect(screen.getByText("You don't have access to this data")).toBeInTheDocument();
    });
    expect(feedbackApi.list).not.toHaveBeenCalled();
  });

  test('lists submissions with type and status for admins', async () => {
    renderView();

    await waitFor(() => {
      expect(screen.getByText('Charts are too slow')).toBeInTheDocument();
    });
    expect(screen.getByText('Export is failing')).toBeInTheDocument();
    expect(feedbackApi.list).toHaveBeenCalled();
  });

  test('requires a note before declining a submission', async () => {
    const user = userEvent.setup();
    renderView();

    await waitFor(() => {
      expect(screen.getByLabelText('Disposition for rating submission')).toBeInTheDocument();
    });
    await user.selectOptions(screen.getByLabelText('Disposition for rating submission'), 'declined');
    await user.click(screen.getByRole('button', { name: 'Save disposition for rating submission' }));

    await waitFor(() => {
      expect(screen.getByText('A note is required when declining or marking a duplicate.')).toBeInTheDocument();
    });
    expect(feedbackApi.update).not.toHaveBeenCalled();
  });

  test('saves a disposition with a note via PATCH', async () => {
    const user = userEvent.setup();
    renderView();

    await waitFor(() => {
      expect(screen.getByLabelText('Disposition for rating submission')).toBeInTheDocument();
    });
    await user.selectOptions(screen.getByLabelText('Disposition for rating submission'), 'declined');
    await user.type(screen.getByLabelText('Disposition note'), 'Duplicate of FB-2, tracked separately');
    await user.click(screen.getByRole('button', { name: 'Save disposition for rating submission' }));

    await waitFor(() => {
      expect(feedbackApi.update).toHaveBeenCalledWith('fb-1', {
        status: 'declined',
        disposition_note: 'Duplicate of FB-2, tracked separately',
      });
    });
    await waitFor(() => {
      expect(screen.getByText('Submission marked as declined.')).toBeInTheDocument();
    });
  });

  test('shows the no-access state when the server 403s the list', async () => {
    feedbackApi.list.mockRejectedValue(new ApiError('Forbidden', 403));
    renderView();

    await waitFor(() => {
      expect(screen.getByText("You don't have access to this data")).toBeInTheDocument();
    });
  });
});
