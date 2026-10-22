import React, { useId, useState } from 'react';

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  inputSize?: 'sm' | 'md' | 'lg';
}

const sizeStyles = {
  sm: { padding: '6px 10px', fontSize: 'var(--text-xs)' },
  md: { padding: '10px 12px', fontSize: 'var(--text-sm)' },
  lg: { padding: '12px 14px', fontSize: 'var(--text-base)' },
};

export const Input: React.FC<InputProps> = ({
  label,
  error,
  hint,
  leftIcon,
  rightIcon,
  inputSize = 'md',
  id,
  style,
  onFocus,
  onBlur,
  ...props
}) => {
  const generatedId = useId();
  const inputId = id || generatedId;
  const hasError = !!error;
  const [focused, setFocused] = useState(false);

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-1)',
    width: '100%',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 'var(--text-sm)',
    fontWeight: 'var(--weight-medium)',
    color: hasError ? 'var(--color-danger)' : 'var(--color-text)',
  };

  const inputWrapperStyle: React.CSSProperties = {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  };

  const borderColor = hasError
    ? 'var(--color-danger)'
    : focused
      ? 'var(--color-primary)'
      : 'var(--color-border-strong)';

  const inputStyle: React.CSSProperties = {
    width: '100%',
    border: `1px solid ${borderColor}`,
    borderRadius: 'var(--radius-md)',
    outline: 'none',
    transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
    boxShadow: focused ? 'var(--focus-ring)' : 'none',
    backgroundColor: props.disabled ? 'var(--color-bg)' : 'var(--color-surface)',
    color: 'var(--color-text)',
    ...sizeStyles[inputSize],
    ...(leftIcon && { paddingLeft: '36px' }),
    ...(rightIcon && { paddingRight: '36px' }),
    ...style,
  };

  return (
    <div style={containerStyle}>
      {label && (
        <label htmlFor={inputId} style={labelStyle}>
          {label}
        </label>
      )}
      <div style={inputWrapperStyle}>
        {leftIcon && (
          <span
            style={{
              position: 'absolute',
              left: '10px',
              color: 'var(--color-text-subtle)',
              display: 'flex',
              pointerEvents: 'none',
            }}
          >
            {leftIcon}
          </span>
        )}
        <input
          id={inputId}
          aria-invalid={hasError}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          style={inputStyle}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          {...props}
        />
        {rightIcon && (
          <span
            style={{
              position: 'absolute',
              right: '10px',
              color: 'var(--color-text-subtle)',
              display: 'flex',
            }}
          >
            {rightIcon}
          </span>
        )}
      </div>
      {error && (
        <span
          id={`${inputId}-error`}
          role="alert"
          style={{ fontSize: 'var(--text-xs)', color: 'var(--color-danger)' }}
        >
          {error}
        </span>
      )}
      {hint && !error && (
        <span
          id={`${inputId}-hint`}
          style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}
        >
          {hint}
        </span>
      )}
    </div>
  );
};
