import React from 'react';
import type { RealtimeConnectionState } from '../../hooks/useRealtimeConnection';

/**
 * Shows how the dashboard receives live metric updates:
 * - "Live" — realtime WebSocket channel connected
 * - "Live (polling)" — REST polling fallback (analytics service has no
 *   WebSocket endpoint yet; see docs/ANALYTICS_DASHBOARD.md)
 */
export const LiveIndicator: React.FC<{ connection: RealtimeConnectionState }> = ({ connection }) => {
  const isLive = connection.mode === 'websocket' && connection.connected;
  const label = isLive ? 'Live' : 'Live (polling)';
  const description = isLive
    ? 'Realtime updates via WebSocket'
    : 'Auto-refreshing via periodic polling';

  return (
    <span
      className={`live-indicator ${isLive ? 'live' : 'polling'}`}
      role="status"
      aria-label={`Dashboard update mode: ${description}`}
      title={description}
    >
      <span className="live-dot" aria-hidden="true" />
      {label}
    </span>
  );
};

export default LiveIndicator;
