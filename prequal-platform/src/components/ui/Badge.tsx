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
  default: { bg: '#f3f4f6', text: '#374151', dot: '#6b7280' },
  success: { bg: '#d1fae5', text: '#065f46', dot: '#10b981' },
  warning: { bg: '#fef3c7', text: '#92400e', dot: '#f59e0b' },
  danger: { bg: '#fee2e2', text: '#991b1b', dot: '#ef4444' },
  info: { bg: '#dbeafe', text: '#1e40af', dot: '#3b82f6' },
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
        gap: size === 'sm' ? '4px' : '6px',
        padding: size === 'sm' ? '2px 6px' : '4px 10px',
        borderRadius: '9999px',
        fontSize: size === 'sm' ? '11px' : '12px',
        fontWeight: 500,
        backgroundColor: styles.bg,
        color: styles.text,
      }}
    >
      {dot && (
        <span
          style={{
            width: size === 'sm' ? '6px' : '8px',
            height: size === 'sm' ? '6px' : '8px',
            borderRadius: '50%',
            backgroundColor: styles.dot,
          }}
        />
      )}
      {children}
    </span>
  );
};