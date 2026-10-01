import React, { useId } from 'react';

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

  return (
    <label
      htmlFor={checkboxId}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <span
        style={{
          position: 'relative',
          width: '18px',
          height: '18px',
          borderRadius: '4px',
          border: `2px solid ${checked || indeterminate ? '#3b82f6' : '#d1d5db'}`,
          backgroundColor: checked || indeterminate ? '#3b82f6' : '#ffffff',
          transition: 'all 0.15s ease',
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
              stroke="#ffffff"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
        {indeterminate && (
          <svg width="10" height="2" viewBox="0 0 10 2" fill="none">
            <rect width="10" height="2" fill="#ffffff" rx="1" />
          </svg>
        )}
      </span>
      {label && (
        <span style={{ fontSize: '14px', color: '#374151' }}>{label}</span>
      )}
    </label>
  );
};