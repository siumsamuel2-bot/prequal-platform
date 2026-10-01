import React, { useId } from 'react';

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  inputSize?: 'sm' | 'md' | 'lg';
}

const sizeStyles = {
  sm: { padding: '6px 10px', fontSize: '12px' },
  md: { padding: '10px 12px', fontSize: '14px' },
  lg: { padding: '12px 14px', fontSize: '16px' },
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
  ...props
}) => {
  const generatedId = useId();
  const inputId = id || generatedId;
  const hasError = !!error;

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    width: '100%',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: '14px',
    fontWeight: 500,
    color: hasError ? '#ef4444' : '#374151',
  };

  const inputWrapperStyle: React.CSSProperties = {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    border: `1px solid ${hasError ? '#ef4444' : props.disabled ? '#d1d5db' : '#d1d5db'}`,
    borderRadius: '6px',
    outline: 'none',
    transition: 'border-color 0.2s, box-shadow 0.2s',
    backgroundColor: props.disabled ? '#f9fafb' : '#ffffff',
    color: '#374151',
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
              color: '#9ca3af',
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
          {...props}
        />
        {rightIcon && (
          <span
            style={{
              position: 'absolute',
              right: '10px',
              color: '#9ca3af',
              display: 'flex',
            }}
          >
            {rightIcon}
          </span>
        )}
      </div>
      {error && (
        <span id={`${inputId}-error`} role="alert" style={{ fontSize: '12px', color: '#ef4444' }}>
          {error}
        </span>
      )}
      {hint && !error && (
        <span id={`${inputId}-hint`} style={{ fontSize: '12px', color: '#6b7280' }}>
          {hint}
        </span>
      )}
    </div>
  );
};