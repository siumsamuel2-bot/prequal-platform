import React, { useId, useState } from 'react';

interface CheckboxProps {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  id?: string;
  indeterminate?: boolean;
}

export const Checkbox: React.FC<CheckboxProps> = ({
  checked = false,
  onChange,
  label,
  disabled = false,
  id,
  indeterminate = false,
}) => {
  const generatedId = useId();
  const checkboxId = id || generatedId;
  const [focused, setFocused] = useState(false);
  const active = checked || indeterminate;

  return (
    <label
      htmlFor={checkboxId}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 'var(--space-2)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <span
        style={{
          position: 'relative',
          width: '18px',
          height: '18px',
          borderRadius: 'var(--radius-sm)',
          border: `2px solid ${active ? 'var(--color-primary)' : 'var(--color-border-strong)'}`,
          backgroundColor: active ? 'var(--color-primary)' : 'var(--color-surface)',
          boxShadow: focused ? 'var(--focus-ring)' : 'none',
          transition: 'background-color var(--transition-fast), border-color var(--transition-fast)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <input
          id={checkboxId}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange?.(e.target.checked)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          disabled={disabled}
          ref={(el) => {
            if (el) el.indeterminate = indeterminate;
          }}
          style={{ position: 'absolute', opacity: 0, width: '100%', height: '100%', cursor: 'inherit' }}
        />
        {checked && !indeterminate && (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path
              d="M10 3L4.5 8.5L2 6"
              stroke="var(--color-text-inverse)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
        {indeterminate && (
          <svg width="10" height="2" viewBox="0 0 10 2" fill="none">
            <rect width="10" height="2" fill="var(--color-text-inverse)" rx="1" />
          </svg>
        )}
      </span>
      {label && <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{label}</span>}
    </label>
  );
};
