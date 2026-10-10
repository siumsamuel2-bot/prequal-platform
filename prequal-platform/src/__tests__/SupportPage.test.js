import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SupportPage from '../components/SupportPage';
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

const renderPage = () =>
  render(
    <ToastProvider>
      <SupportPage />
      <ToastContainer />
    </ToastProvider>
  );

describe('SupportPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    feedbackApi.submit.mockResolvedValue({ id: 'fb-1' });
  });

  test('renders contact email, request form, and known issues', () => {
    renderPage();

    expect(screen.getByRole('link', { name: 'support@prequal.app' })).toBeInTheDocument();
    expect(screen.getByRole('form', { name: 'Support request form' })).toBeInTheDocument();
    expect(screen.getByLabelText('Known issues')).toBeInTheDocument();
    expect(screen.getByText('Platform analytics panels are admin-only')).toBeInTheDocument();
    expect(screen.getByText('State credential syncs can lag behind state databases')).toBeInTheDocument();
  });

  test('submits a support request and confirms with a toast', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText('Support message'), 'Export is failing on my roster');
    await user.click(screen.getByRole('button', { name: 'Send support request' }));

    await waitFor(() => {
      expect(feedbackApi.submit).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'support', surface: 'contact_page', message: 'Export is failing on my roster' })
      );
    });
    await waitFor(() => {
      expect(screen.getByText('Support request sent. We will get back to you within one business day.')).toBeInTheDocument();
    });
  });

  test('shows the unavailable state on 403', async () => {
    const user = userEvent.setup();
    feedbackApi.submit.mockRejectedValue(new ApiError('Forbidden', 403));
    renderPage();

    await user.type(screen.getByLabelText('Support message'), 'Help');
    await user.click(screen.getByRole('button', { name: 'Send support request' }));

    await waitFor(() => {
      expect(screen.getByText('Support requests are unavailable for your account')).toBeInTheDocument();
    });
  });
});
