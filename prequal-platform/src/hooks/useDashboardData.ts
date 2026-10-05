import { useCallback, useEffect, useRef, useState } from 'react';

export interface DashboardDataState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  lastRefreshedAt: Date | null;
  refetch: () => void;
}

/**
 * Fetches dashboard data with automatic refresh support.
 *
 * Polling keeps dashboards live when a realtime WebSocket channel is not
 * available (the analytics service currently exposes REST only — see
 * docs/ANALYTICS_DASHBOARD.md). When `isRealtimeLive` is true the poll
 * interval is stretched because the WebSocket pushes updates.
 */
export function useDashboardData<T>(
  fetcher: () => Promise<T>,
  options: { refreshIntervalMs?: number; isRealtimeLive?: boolean; enabled?: boolean } = {},
): DashboardDataState<T> {
  const { refreshIntervalMs = 30000, isRealtimeLive = false, enabled = true } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const hasDataRef = useRef(false);

  const load = useCallback(async () => {
    if (!enabled) return;
    if (!hasDataRef.current) setLoading(true);
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
      hasDataRef.current = true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load dashboard data';
      if (!hasDataRef.current) setError(message);
    } finally {
      setLoading(false);
      setLastRefreshedAt(new Date());
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    hasDataRef.current = false;
    setData(null);
    load();
  }, [enabled, load]);

  useEffect(() => {
    if (!enabled || refreshIntervalMs <= 0) return;
    // When the WebSocket channel is live we only need a slow safety net poll.
    const interval = isRealtimeLive ? refreshIntervalMs * 3 : refreshIntervalMs;
    const timer = window.setInterval(load, interval);
    return () => window.clearInterval(timer);
  }, [enabled, refreshIntervalMs, isRealtimeLive, load]);

  return { data, loading, error, lastRefreshedAt, refetch: load };
}
