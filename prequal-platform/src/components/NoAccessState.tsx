import React from 'react';
import { ApiError } from '../api/client';

export type AccessNoticeVariant = 'no-access' | 'no-data';

interface NoAccessStateProps {
  variant?: AccessNoticeVariant;
  title?: string;
  description?: string;
  action?: React.ReactNode;
}

const DEFAULT_CONTENT: Record<AccessNoticeVariant, { title: string; description: string }> = {
  'no-access': {
    title: "You don't have access to this data",
    description:
      'This section is only available to accounts with the right permissions or team membership. If you think you should have access, ask your administrator to check your account setup.',
  },
  'no-data': {
    title: 'No data for your team',
    description:
      "There's nothing to show here yet. Data will appear once your team has activity that feeds this view.",
  },
};

export const isForbiddenError = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 403;

export const NoAccessState: React.FC<NoAccessStateProps> = ({
  variant = 'no-access',
  title,
  description,
  action,
}) => {
  const defaults = DEFAULT_CONTENT[variant];

  return (
    <div
      role="status"
      aria-live="polite"
      data-variant={variant}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        margin: '16px auto',
        textAlign: 'center',
        backgroundColor: '#f9fafb',
        border: '1px solid #e5e7eb',
        borderRadius: '12px',
        maxWidth: '560px',
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      <div
        aria-hidden="true"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '56px',
          height: '56px',
          marginBottom: '16px',
          borderRadius: '50%',
          backgroundColor: '#eff6ff',
          color: '#3b82f6',
        }}
      >
        <svg width="28" height="28" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {variant === 'no-access' ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-5.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293H11.414a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 007.586 13H4"
            />
          )}
        </svg>
      </div>
      <h3
        style={{
          fontSize: '18px',
          fontWeight: 600,
          color: '#374151',
          margin: '0 0 8px',
        }}
      >
        {title ?? defaults.title}
      </h3>
      <p
        style={{
          fontSize: '14px',
          color: '#6b7280',
          margin: '0 0 16px',
          maxWidth: '420px',
          lineHeight: 1.5,
        }}
      >
        {description ?? defaults.description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
};
