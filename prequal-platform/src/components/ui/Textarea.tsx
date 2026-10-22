import React, { useId, useState } from 'react';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Textarea: React.FC<TextareaProps> = ({
  label,
  error,
  hint,
  id,
  style,
  onFocus,
  onBlur,
  ...props
}) => {
  const generatedId = useId();
  const textareaId = id || `textarea-${generatedId}`;
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

  const borderColor = hasError
    ? 'var(--color-danger)'
    : focused
      ? 'var(--color-primary)'
      : 'var(--color-border-strong)';

  const textareaStyle: React.CSSProperties = {
    width: '100%',
    minHeight: '100px',
    padding: '10px 12px',
    fontSize: 'var(--text-sm)',
    fontFamily: 'inherit',
    border: `1px solid ${borderColor}`,
    borderRadius: 'var(--radius-md)',
    outline: 'none',
    transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
    boxShadow: focused ? 'var(--focus-ring)' : 'none',
    backgroundColor: props.disabled ? 'var(--color-bg)' : 'var(--color-surface)',
    color: 'var(--color-text)',
    resize: 'vertical',
    lineHeight: 'var(--leading-normal)',
    ...style,
  };

  return (
    <div style={containerStyle}>
      {label && (
        <label htmlFor={textareaId} style={labelStyle}>
          {label}
        </label>
      )}
      <textarea
        id={textareaId}
        aria-invalid={hasError}
        aria-describedby={
          error ? `${textareaId}-error` : hint ? `${textareaId}-hint` : undefined
        }
        style={textareaStyle}
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
      {error && (
        <span
          id={`${textareaId}-error`}
          style={{ fontSize: 'var(--text-xs)', color: 'var(--color-danger)' }}
          role="alert"
        >
          {error}
        </span>
      )}
      {hint && !error && (
        <span
          id={`${textareaId}-hint`}
          style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}
        >
          {hint}
        </span>
      )}
    </div>
  );
};
