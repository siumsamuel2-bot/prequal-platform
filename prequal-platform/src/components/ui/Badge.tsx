import React from 'react';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';
type BadgeSize = 'sm' | 'md';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, { bg: string; text: string; dot: string }> = {
  default: {
    bg: 'var(--color-surface-muted)',
    text: 'var(--color-text)',
    dot: 'var(--color-text-muted)',
  },
  success: {
    bg: 'var(--color-success-soft)',
    text: 'var(--color-success-strong)',
    dot: 'var(--color-success)',
  },
  warning: {
    bg: 'var(--color-warning-soft)',
    text: 'var(--color-warning-strong)',
    dot: 'var(--color-warning)',
  },
  danger: {
    bg: 'var(--color-danger-soft)',
    text: 'var(--color-danger-strong)',
    dot: 'var(--color-danger)',
  },
  info: {
    bg: 'var(--color-info-soft)',
    text: 'var(--color-info-strong)',
    dot: 'var(--color-info)',
  },
};

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
}) => {
  const styles = variantStyles[variant];

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: size === 'sm' ? 'var(--space-1)' : '6px',
        padding: size === 'sm' ? '2px 6px' : '4px 10px',
        borderRadius: 'var(--radius-full)',
        fontSize: size === 'sm' ? '11px' : 'var(--text-xs)',
        fontWeight: 'var(--weight-medium)',
        backgroundColor: styles.bg,
        color: styles.text,
      }}
    >
      {dot && (
        <span
          style={{
            width: size === 'sm' ? '6px' : '8px',
            height: size === 'sm' ? '6px' : '8px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: styles.dot,
          }}
        />
      )}
      {children}
    </span>
  );
};
