import React, { useState, useRef, useEffect, useId } from 'react';

type TooltipPosition = 'top' | 'bottom' | 'left' | 'right';

interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  position?: TooltipPosition;
  delay?: number;
}

const positionStyles: Record<TooltipPosition, React.CSSProperties> = {
  top: {
    bottom: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    marginBottom: '6px',
  },
  bottom: {
    top: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    marginTop: '6px',
  },
  left: {
    right: '100%',
    top: '50%',
    transform: 'translateY(-50%)',
    marginRight: '6px',
  },
  right: {
    left: '100%',
    top: '50%',
    transform: 'translateY(-50%)',
    marginLeft: '6px',
  },
};

const arrowStyles: Record<TooltipPosition, React.CSSProperties> = {
  top: {
    top: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    borderTopColor: '#1f2937',
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: 'transparent',
  },
  bottom: {
    bottom: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    borderBottomColor: '#1f2937',
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderTopColor: 'transparent',
  },
  left: {
    left: '100%',
    top: '50%',
    transform: 'translateY(-50%)',
    borderLeftColor: '#1f2937',
    borderTopColor: 'transparent',
    borderBottomColor: 'transparent',
    borderRightColor: 'transparent',
  },
  right: {
    right: '100%',
    top: '50%',
    transform: 'translateY(-50%)',
    borderRightColor: '#1f2937',
    borderTopColor: 'transparent',
    borderBottomColor: 'transparent',
    borderLeftColor: 'transparent',
  },
};

export const Tooltip: React.FC<TooltipProps> = ({
  content,
  children,
  position = 'top',
  delay = 200,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const generatedTooltipId = useId();
  const tooltipId = `tooltip-${generatedTooltipId.replace(/[^a-zA-Z0-9-]/g, '')}`;
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const show = () => {
    timeoutRef.current = setTimeout(() => setIsVisible(true), delay);
  };

  const hide = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const child = React.cloneElement(children, {
    'aria-describedby': isVisible ? tooltipId : undefined,
    onMouseEnter: (e: React.MouseEvent) => {
      show();
      children.props.onMouseEnter?.(e);
    },
    onMouseLeave: (e: React.MouseEvent) => {
      hide();
      children.props.onMouseLeave?.(e);
    },
    onFocus: (e: React.FocusEvent) => {
      setIsVisible(true);
      children.props.onFocus?.(e);
    },
    onBlur: (e: React.FocusEvent) => {
      setIsVisible(false);
      children.props.onBlur?.(e);
    },
  });

  return (
    <span style={{ position: 'relative', display: 'inline-flex' }}>
      {child}
      {isVisible && (
        <span
          id={tooltipId}
          role="tooltip"
          style={{
            position: 'absolute',
            zIndex: 9999,
            ...positionStyles[position],
          }}
        >
          <span
            style={{
              display: 'block',
              backgroundColor: '#1f2937',
              color: '#ffffff',
              fontSize: '12px',
              padding: '6px 10px',
              borderRadius: '6px',
              whiteSpace: 'nowrap',
              maxWidth: '250px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
            }}
          >
            {content}
          </span>
          <span
            style={{
              position: 'absolute',
              width: 0,
              height: 0,
              borderStyle: 'solid',
              borderWidth: '5px',
              ...arrowStyles[position],
            }}
          />
        </span>
      )}
    </span>
  );
};