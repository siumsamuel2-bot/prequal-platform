import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    backgroundColor: 'var(--color-primary)',
    color: 'var(--color-text-inverse)',
    border: '1px solid transparent',
  },
  secondary: {
    backgroundColor: 'var(--color-surface)',
    color: 'var(--color-text)',
    border: '1px solid var(--color-border-strong)',
  },
  danger: {
    backgroundColor: 'var(--color-danger)',
    color: 'var(--color-text-inverse)',
    border: '1px solid transparent',
  },
  ghost: {
    backgroundColor: 'transparent',
    color: 'var(--color-text)',
    border: '1px solid transparent',
  },
};

const hoverBackground: Record<ButtonVariant, string> = {
  primary: 'var(--color-primary-hover)',
  secondary: 'var(--color-surface-muted)',
  danger: 'var(--color-danger-hover)',
  ghost: 'var(--color-surface-muted)',
};

const sizeStyles: Record<ButtonSize, React.CSSProperties> = {
  sm: { padding: '6px 12px', fontSize: 'var(--text-xs)', borderRadius: 'var(--radius-sm)' },
  md: { padding: '8px 16px', fontSize: 'var(--text-sm)', borderRadius: 'var(--radius-md)' },
  lg: { padding: '12px 24px', fontSize: 'var(--text-base)', borderRadius: 'var(--radius-lg)' },
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  leftIcon,
  rightIcon,
  children,
  disabled,
  style,
  ...props
}) => {
  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 'var(--space-2)',
    fontWeight: 'var(--weight-medium)',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled || loading ? 0.6 : 1,
    transition: 'background-color var(--transition-fast), transform var(--transition-fast)',
    width: fullWidth ? '100%' : 'auto',
    ...variantStyles[variant],
    ...sizeStyles[size],
    ...style,
  };

  return (
    <button
      {...props}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      style={baseStyle}
      onMouseEnter={(e) => {
        if (!disabled && !loading) {
          e.currentTarget.style.backgroundColor = hoverBackground[variant];
          e.currentTarget.style.transform = 'translateY(-1px)';
        }
        props.onMouseEnter?.(e);
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = variantStyles[variant].backgroundColor ?? '';
        e.currentTarget.style.transform = 'translateY(0)';
        props.onMouseLeave?.(e);
      }}
    >
      {loading && (
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          style={{ animation: 'spin 1s linear infinite' }}
        >
          <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.3" />
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
      )}
      {!loading && leftIcon && <span style={{ display: 'flex' }}>{leftIcon}</span>}
      {children}
      {!loading && rightIcon && <span style={{ display: 'flex' }}>{rightIcon}</span>}
    </button>
  );
};
