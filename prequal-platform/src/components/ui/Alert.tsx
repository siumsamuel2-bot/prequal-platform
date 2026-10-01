import React from 'react';

type AlertVariant = 'info' | 'success' | 'warning' | 'error';

interface AlertProps {
  children: React.ReactNode;
  variant?: AlertVariant;
  title?: string;
  onClose?: () => void;
  icon?: React.ReactNode;
}

const variantConfig: Record<AlertVariant, { bg: string; border: string; iconColor: string; icon: React.ReactNode }> = {
  info: {
    bg: '#eff6ff',
    border: '#3b82f6',
    iconColor: '#3b82f6',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
      </svg>
    ),
  },
  success: {
    bg: '#ecfdf5',
    border: '#10b981',
    iconColor: '#10b981',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
      </svg>
    ),
  },
  warning: {
    bg: '#fffbeb',
    border: '#f59e0b',
    iconColor: '#f59e0b',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
    ),
  },
  error: {
    bg: '#fef2f2',
    border: '#ef4444',
    iconColor: '#ef4444',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
      </svg>
    ),
  },
};

export const Alert: React.FC<AlertProps> = ({
  children,
  variant = 'info',
  title,
  onClose,
  icon,
}) => {
  const config = variantConfig[variant];

  return (
    <div
      role="alert"
      style={{
        padding: '12px 16px',
        borderRadius: '8px',
        backgroundColor: config.bg,
        borderLeft: `4px solid ${config.border}`,
        display: 'flex',
        gap: '12px',
        alignItems: 'flex-start',
      }}
    >
      <span style={{ color: config.iconColor, flexShrink: 0, marginTop: '2px' }}>
        {icon || config.icon}
      </span>
      <div style={{ flex: 1 }}>
        {title && (
          <h4 style={{ fontSize: '14px', fontWeight: 600, color: '#374151', margin: '0 0 4px 0' }}>
            {title}
          </h4>
        )}
        <div style={{ fontSize: '14px', color: '#4b5563', lineHeight: 1.5 }}>
          {children}
        </div>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            padding: '2px',
            cursor: 'pointer',
            color: '#9ca3af',
            borderRadius: '4px',
            flexShrink: 0,
          }}
          aria-label="Dismiss"
        >
          <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
            <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" />
          </svg>
        </button>
      )}
    </div>
  );
};