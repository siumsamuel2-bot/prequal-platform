import React from 'react';

interface CardProps {
  children: React.ReactNode;
  title?: string;
  description?: string;
  action?: React.ReactNode;
  noPadding?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export const Card: React.FC<CardProps> = ({
  children,
  title,
  description,
  action,
  noPadding = false,
  className,
  style,
}) => {
  return (
    <div
      className={className}
      style={{
        backgroundColor: 'var(--color-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-sm)',
        overflow: 'hidden',
        ...style,
      }}
    >
      {(title || action) && (
        <div
          style={{
            padding: 'var(--space-4) var(--space-5)',
            borderBottom: '1px solid var(--color-border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            {title && (
              <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-semibold)', color: 'var(--color-text)', margin: 0 }}>
                {title}
              </h3>
            )}
            {description && (
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)', margin: 'var(--space-1) 0 0 0' }}>
                {description}
              </p>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      <div style={{ padding: noPadding ? 0 : 'var(--space-5)' }}>{children}</div>
    </div>
  );
};

interface CardHeaderProps {
  children: React.ReactNode;
  className?: string;
}

export const CardHeader: React.FC<CardHeaderProps> = ({ children, className }) => (
  <div
    className={className}
    style={{
      padding: 'var(--space-4) var(--space-5)',
      borderBottom: '1px solid var(--color-border)',
    }}
  >
    {children}
  </div>
);

interface CardContentProps {
  children: React.ReactNode;
  className?: string;
}

export const CardContent: React.FC<CardContentProps> = ({ children, className }) => (
  <div className={className} style={{ padding: 'var(--space-5)' }}>
    {children}
  </div>
);

interface CardFooterProps {
  children: React.ReactNode;
  className?: string;
}

export const CardFooter: React.FC<CardFooterProps> = ({ children, className }) => (
  <div
    className={className}
    style={{
      padding: 'var(--space-4) var(--space-5)',
      borderTop: '1px solid var(--color-border)',
      backgroundColor: 'var(--color-bg)',
    }}
  >
    {children}
  </div>
);
