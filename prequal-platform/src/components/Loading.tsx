import React from 'react';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className = '' }) => {
  const sizeMap = {
    sm: '20px',
    md: '32px',
    lg: '48px',
  };

  const strokeWidthMap = {
    sm: 2,
    md: 3,
    lg: 4,
  };

  return (
    <svg
      className={className}
      width={sizeMap[size]}
      height={sizeMap[size]}
      viewBox="0 0 24 24"
      fill="none"
      style={{ animation: 'spin 1s linear infinite' }}
    >
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="#e5e7eb"
        strokeWidth={strokeWidthMap[size]}
      />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="#3b82f6"
        strokeWidth={strokeWidthMap[size]}
        strokeLinecap="round"
      />
    </svg>
  );
};

interface LoadingProps {
  message?: string;
  fullScreen?: boolean;
}

export const Loading: React.FC<LoadingProps> = ({ message = 'Loading...', fullScreen = false }) => {
  const content = (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px',
        gap: '16px',
      }}
    >
      <Spinner size="lg" />
      <span style={{ fontSize: '14px', color: '#6b7280' }}>{message}</span>
    </div>
  );

  if (fullScreen) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          backgroundColor: '#f9fafb',
        }}
      >
        {content}
      </div>
    );
  }

  return content;
};

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = '20px',
  borderRadius = '4px',
  className = '',
}) => {
  return (
    <div
      className={className}
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: '#e5e7eb',
        animation: 'pulse 1.5s ease-in-out infinite',
      }}
    >
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
};

interface SkeletonTableProps {
  rows?: number;
  columns?: number;
}

export const SkeletonTable: React.FC<SkeletonTableProps> = ({ rows = 5, columns = 4 }) => {
  return (
    <div style={{ width: '100%' }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gap: '12px',
          padding: '16px',
          borderBottom: '1px solid #e5e7eb',
        }}
      >
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={`header-${i}`} height={16} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div
          key={`row-${rowIndex}`}
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${columns}, 1fr)`,
            gap: '12px',
            padding: '16px',
            borderBottom: '1px solid #f3f4f6',
          }}
        >
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton key={`cell-${rowIndex}-${colIndex}`} height={14} />
          ))}
        </div>
      ))}
    </div>
  );
};