import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import FeedbackWidget from '../components/FeedbackWidget';
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

const renderWidget = (surface = 'analytics_dashboard') =>
  render(
    <MemoryRouter>
      <FeedbackWidget surface={surface} />
    </MemoryRouter>
  );

describe('FeedbackWidget', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    feedbackApi.submit.mockResolvedValue({ id: 'fb-1' });
  });

  test('renders the idle prompt with accessible thumbs buttons', () => {
    renderWidget();

    expect(screen.getByText('How is this dashboard working for you?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'This dashboard works well' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'This dashboard needs work' })).toBeInTheDocument();
  });

  test('submits a rating with optional message and shows the thank-you state', async () => {
    const user = userEvent.setup();
    renderWidget();

    await user.click(screen.getByRole('button', { name: 'This dashboard works well' }));
    expect(screen.getByLabelText('Feedback message')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Feedback message'), 'Great charts');
    await user.click(screen.getByRole('button', { name: 'Send feedback' }));

    await waitFor(() => {
      expect(screen.getByRole('status')).toBeInTheDocument();
    });
    expect(feedbackApi.submit).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'rating', surface: 'analytics_dashboard', rating: 5, message: 'Great charts' })
    );
    expect(screen.getByText('Thanks — your feedback was sent.')).toBeInTheDocument();
    expect(screen.getByText('Contact support')).toBeInTheDocument();
  });

  test('shows an inline alert and keeps retry available on failure', async () => {
    const user = userEvent.setup();
    feedbackApi.submit.mockRejectedValue(new ApiError('Server error', 500));
    renderWidget();

    await user.click(screen.getByRole('button', { name: 'This dashboard needs work' }));
    await user.click(screen.getByRole('button', { name: 'Send feedback' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText('Could not send your feedback. Please try again.')).toBeInTheDocument();

    feedbackApi.submit.mockResolvedValue({ id: 'fb-2' });
    await user.click(screen.getByRole('button', { name: 'Send feedback' }));

    await waitFor(() => {
      expect(screen.getByText('Thanks — your feedback was sent.')).toBeInTheDocument();
    });
  });

  test('dismiss returns the widget to the idle prompt', async () => {
    const user = userEvent.setup();
    renderWidget();

    await user.click(screen.getByRole('button', { name: 'This dashboard works well' }));
    await user.click(screen.getByRole('button', { name: 'Send feedback' }));
    await waitFor(() => {
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Dismiss feedback widget' }));
    expect(screen.getByText('How is this dashboard working for you?')).toBeInTheDocument();
  });
});
