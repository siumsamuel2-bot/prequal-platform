import { useCallback, useEffect, useRef, useState } from 'react';

export type RealtimeConnectionMode = 'websocket' | 'polling' | 'disabled';

export interface RealtimeConnectionState {
  mode: RealtimeConnectionMode;
  connected: boolean;
  lastMessageAt: Date | null;
  /** Manually bump `lastMessageAt` to signal a refresh (used by polling fallbacks). */
  refreshTimestamp: () => void;
}

export interface RealtimeMessage {
  type: string;
  payload?: Record<string, unknown>;
}

interface RealtimeOptions {
  /**
   * WebSocket URL of the analytics realtime channel. The analytics service
   * does not expose a WebSocket endpoint yet (MID-592 tracks this as a
   * backend follow-up). When the URL is unset — or the connection fails —
   * consumers transparently fall back to interval polling.
   */
  url?: string;
  /** Called for every parsed JSON message received on the socket. */
  onMessage?: (message: RealtimeMessage) => void;
  /** Called when the socket drops and polling fallback takes over. */
  onFallback?: () => void;
  /** Base reconnect backoff in ms. Doubles on consecutive failures. */
  reconnectBaseDelayMs?: number;
  maxReconnectAttempts?: number;
}

const DEFAULT_BASE_DELAY_MS = 2000;
const DEFAULT_MAX_ATTEMPTS = 3;

export function useRealtimeConnection({
  url,
  onMessage,
  onFallback,
  reconnectBaseDelayMs = DEFAULT_BASE_DELAY_MS,
  maxReconnectAttempts = DEFAULT_MAX_ATTEMPTS,
}: RealtimeOptions): RealtimeConnectionState {
  const [mode, setMode] = useState<RealtimeConnectionMode>(url ? 'websocket' : 'polling');
  const [connected, setConnected] = useState(false);
  const [lastMessageAt, setLastMessageAt] = useState<Date | null>(null);

  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const onFallbackRef = useRef(onFallback);
  onFallbackRef.current = onFallback;

  useEffect(() => {
    if (!url || typeof WebSocket === 'undefined') {
      setMode('polling');
      return;
    }

    let socket: WebSocket | null = null;
    let attempts = 0;
    let reconnectTimer: number | null = null;
    let cancelled = false;
    let fellBack = false;

    const fallbackToPolling = () => {
      if (fellBack) return;
      fellBack = true;
      setMode('polling');
      setConnected(false);
      onFallbackRef.current?.();
    };

    const connect = () => {
      if (cancelled) return;
      try {
        socket = new WebSocket(url);
      } catch {
        // Invalid URL or blocked WebSocket support: fall back to polling.
        fallbackToPolling();
        return;
      }

      socket.onopen = () => {
        attempts = 0;
        fellBack = false;
        setMode('websocket');
        setConnected(true);
      };

      socket.onmessage = (event: MessageEvent) => {
        setLastMessageAt(new Date());
        try {
          const parsed = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
          if (parsed && typeof parsed === 'object' && 'type' in parsed) {
            onMessageRef.current?.(parsed as RealtimeMessage);
          }
        } catch {
          // Non-JSON frames are ignored; the connection stays up.
        }
      };

      socket.onerror = () => {
        socket?.close();
      };

      socket.onclose = () => {
        setConnected(false);
        if (cancelled || fellBack) return;
        attempts += 1;
        if (attempts > maxReconnectAttempts) {
          fallbackToPolling();
          return;
        }
        const delay = reconnectBaseDelayMs * Math.pow(2, attempts - 1);
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close();
      setConnected(false);
    };
  }, [url, reconnectBaseDelayMs, maxReconnectAttempts]);

  const refreshTimestamp = useCallback(() => setLastMessageAt(new Date()), []);

  return { mode, connected, lastMessageAt, refreshTimestamp };
}
