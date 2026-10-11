import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import WhatsNew from '../components/WhatsNew';
import Header from '../components/Header';
import { RELEASE_NOTES } from '../data/releaseNotes';
import { WHATS_NEW_STORAGE_KEY } from '../hooks/useWhatsNew';

describe('WhatsNew drawer', () => {
  test('renders nothing when closed', () => {
    render(<WhatsNew isOpen={false} onClose={() => {}} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('renders the latest release notes in an accessible dialog', () => {
    render(<WhatsNew isOpen onClose={() => {}} />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('heading', { name: "What's New" })).toBeInTheDocument();
    expect(screen.getByText(`v${RELEASE_NOTES[0].version}`)).toBeInTheDocument();
    expect(screen.getByText(RELEASE_NOTES[0].title)).toBeInTheDocument();
    // Category labels come through as visible badges (one per release).
    expect(screen.getAllByText('Added').length).toBeGreaterThan(0);
  });

  test('shows a branded empty state when there are no notes', () => {
    render(<WhatsNew isOpen onClose={() => {}} notes={[]} />);
    expect(screen.getByText("You're all caught up")).toBeInTheDocument();
    expect(screen.queryByText(`v${RELEASE_NOTES[0].version}`)).not.toBeInTheDocument();
  });

  test('closes via the close button and the Escape key', async () => {
    const onClose = jest.fn();
    const user = userEvent.setup();
    render(<WhatsNew isOpen onClose={onClose} />);

    await user.click(screen.getByRole('button', { name: "Close What's New" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});

describe("Header What's New entry", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  test('shows the unseen dot, opens the drawer, and clears the dot', async () => {
    const user = userEvent.setup();
    render(<Header />);

    expect(screen.getByTestId('whats-new-dot')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /What's New/ }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(window.localStorage.getItem(WHATS_NEW_STORAGE_KEY)).toBe(RELEASE_NOTES[0].version);
    expect(screen.queryByTestId('whats-new-dot')).not.toBeInTheDocument();
  });

  test('hides the dot when the latest version has already been seen', () => {
    window.localStorage.setItem(WHATS_NEW_STORAGE_KEY, RELEASE_NOTES[0].version);
    render(<Header />);
    expect(screen.queryByTestId('whats-new-dot')).not.toBeInTheDocument();
  });
});
