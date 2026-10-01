import React, { useMemo } from 'react';

type AvatarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface AvatarProps {
  name: string;
  src?: string;
  size?: AvatarSize;
}

const sizeMap: Record<AvatarSize, { container: number; font: number }> = {
  xs: { container: 24, font: 10 },
  sm: { container: 32, font: 12 },
  md: { container: 40, font: 14 },
  lg: { container: 48, font: 16 },
  xl: { container: 64, font: 20 },
};

const colors = [
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#ec4899',
  '#06b6d4',
  '#f97316',
];

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) {
    return parts[0].charAt(0).toUpperCase();
  }
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

function getColorFromName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export const Avatar: React.FC<AvatarProps> = ({ name, src, size = 'md' }) => {
  const { container: containerSize, font: fontSize } = sizeMap[size];

  const initials = useMemo(() => getInitials(name), [name]);
  const bgColor = useMemo(() => getColorFromName(name), [name]);

  const containerStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: `${containerSize}px`,
    height: `${containerSize}px`,
    borderRadius: '50%',
    fontSize: `${fontSize}px`,
    fontWeight: 600,
    color: '#ffffff',
    backgroundColor: src ? '#e5e7eb' : bgColor,
    overflow: 'hidden',
    flexShrink: 0,
  };

  if (src) {
    return (
      <span style={containerStyle} role="img" aria-label={name}>
        <img
          src={src}
          alt=""
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          onError={(e) => {
            const target = e.target as HTMLImageElement;
            target.style.display = 'none';
          }}
        />
      </span>
    );
  }

  return (
    <span style={containerStyle} role="img" aria-label={name} title={name}>
      {initials}
    </span>
  );
};

interface AvatarGroupProps {
  children: React.ReactNode;
  max?: number;
}

export const AvatarGroup: React.FC<AvatarGroupProps> = ({ children, max = 4 }) => {
  const childArray = React.Children.toArray(children);
  const visibleChildren = childArray.slice(0, max);
  const remainingCount = childArray.length - max;

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      {visibleChildren.map((child, index) => (
        <div
          key={index}
          style={{
            marginLeft: index === 0 ? 0 : '-8px',
            zIndex: visibleChildren.length - index,
            border: '2px solid #ffffff',
            borderRadius: '50%',
          }}
        >
          {child}
        </div>
      ))}
      {remainingCount > 0 && (
        <div
          style={{
            marginLeft: '-8px',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            backgroundColor: '#e5e7eb',
            border: '2px solid #ffffff',
            fontSize: '11px',
            fontWeight: 600,
            color: '#6b7280',
            zIndex: 0,
          }}
          title={`${remainingCount} more`}
        >
          +{remainingCount}
        </div>
      )}
    </div>
  );
};