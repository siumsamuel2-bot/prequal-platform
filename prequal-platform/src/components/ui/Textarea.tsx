import React, { useId } from 'react';

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
  ...props
}) => {
  const generatedId = useId();
  const textareaId = id || `textarea-${generatedId}`;
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

  const textareaStyle: React.CSSProperties = {
    width: '100%',
    minHeight: '100px',
    padding: '10px 12px',
    fontSize: '14px',
    fontFamily: 'inherit',
    border: `1px solid ${hasError ? '#ef4444' : props.disabled ? '#d1d5db' : '#d1d5db'}`,
    borderRadius: '6px',
    outline: 'none',
    transition: 'border-color 0.2s, box-shadow 0.2s',
    backgroundColor: props.disabled ? '#f9fafb' : '#ffffff',
    color: '#374151',
    resize: 'vertical',
    lineHeight: 1.5,
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
        {...props}
      />
      {error && (
        <span id={`${textareaId}-error`} style={{ fontSize: '12px', color: '#ef4444' }} role="alert">
          {error}
        </span>
      )}
      {hint && !error && (
        <span id={`${textareaId}-hint`} style={{ fontSize: '12px', color: '#6b7280' }}>
          {hint}
        </span>
      )}
    </div>
  );
};