import React, { useState, useRef, useEffect, useId } from 'react';

interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps {
  options: SelectOption[];
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  label?: string;
  error?: string;
  disabled?: boolean;
  id?: string;
}

export const Select: React.FC<SelectProps> = ({
  options,
  value,
  onChange,
  placeholder = 'Select an option',
  label,
  error,
  disabled = false,
  id,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [focused, setFocused] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const generatedId = useId();
  const selectId = id || generatedId;

  const selectedOption = options.find((opt) => opt.value === value);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    switch (e.key) {
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (isOpen && highlightedIndex >= 0) {
          const option = options[highlightedIndex];
          if (!option.disabled) {
            onChange?.(option.value);
            setIsOpen(false);
          }
        } else {
          setIsOpen(true);
        }
        break;
      case 'ArrowDown':
        e.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
        } else {
          setHighlightedIndex((prev) => (prev < options.length - 1 ? prev + 1 : prev));
        }
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (isOpen) {
          setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : prev));
        }
        break;
      case 'Escape':
        setIsOpen(false);
        break;
    }
  };

  const triggerBorder = error
    ? 'var(--color-danger)'
    : focused || isOpen
      ? 'var(--color-primary)'
      : 'var(--color-border-strong)';

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      {label && (
        <label
          htmlFor={selectId}
          style={{
            display: 'block',
            fontSize: 'var(--text-sm)',
            fontWeight: 'var(--weight-medium)',
            color: error ? 'var(--color-danger)' : 'var(--color-text)',
            marginBottom: 'var(--space-1)',
          }}
        >
          {label}
        </label>
      )}
      <button
        id={selectId}
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-invalid={!!error}
        aria-describedby={error ? `${selectId}-error` : undefined}
        disabled={disabled}
        style={{
          width: '100%',
          padding: '10px 12px',
          fontSize: 'var(--text-sm)',
          borderRadius: 'var(--radius-md)',
          border: `1px solid ${triggerBorder}`,
          boxShadow: focused || isOpen ? 'var(--focus-ring)' : 'none',
          backgroundColor: disabled ? 'var(--color-bg)' : 'var(--color-surface)',
          color: selectedOption ? 'var(--color-text)' : 'var(--color-text-subtle)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          textAlign: 'left',
          transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
        }}
      >
        <span>{selectedOption?.label || placeholder}</span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 20 20"
          fill="currentColor"
          style={{
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0)',
            transition: 'transform var(--transition-fast)',
          }}
        >
          <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
        </svg>
      </button>
      {isOpen && (
        <ul
          role="listbox"
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 'var(--space-1)',
            padding: 'var(--space-1)',
            backgroundColor: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 10,
            maxHeight: '200px',
            overflowY: 'auto',
            listStyle: 'none',
          }}
        >
          {options.map((option, index) => (
            <li
              key={option.value}
              role="option"
              aria-selected={option.value === value}
              aria-disabled={option.disabled || undefined}
              onClick={() => {
                if (!option.disabled) {
                  onChange?.(option.value);
                  setIsOpen(false);
                }
              }}
              onMouseEnter={() => setHighlightedIndex(index)}
              style={{
                padding: '8px 12px',
                fontSize: 'var(--text-sm)',
                borderRadius: 'var(--radius-sm)',
                cursor: option.disabled ? 'not-allowed' : 'pointer',
                backgroundColor:
                  highlightedIndex === index ? 'var(--color-surface-muted)' : 'transparent',
                color: option.disabled ? 'var(--color-text-subtle)' : 'var(--color-text)',
              }}
            >
              {option.label}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <span
          id={`${selectId}-error`}
          role="alert"
          style={{ fontSize: 'var(--text-xs)', color: 'var(--color-danger)', marginTop: 'var(--space-1)' }}
        >
          {error}
        </span>
      )}
    </div>
  );
};
