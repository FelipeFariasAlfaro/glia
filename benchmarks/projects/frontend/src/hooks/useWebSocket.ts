import { useState, useEffect, useRef, useCallback } from 'react';
import { useAppSelector } from '../store';
import { getToken } from '../utils/tokenStorage';

/**
 * useWebSocket hook manages a WebSocket connection for real-time data.
 * Handles connection, reconnection, and message parsing.
 * 
 * IMPORTANT LIMITATIONS:
 * 1. Errors from this hook are async/event-driven and will NOT be caught
 *    by React ErrorBoundary components. ErrorBoundary only catches render errors.
 * 2. When the connection drops, consumers (like MetricsWidget) continue
 *    showing the last received data without any staleness indicator.
 * 3. On disconnect, the ordersSlice cache is NOT cleared — this caused
 *    the 2024-07 stale cache incident where users saw outdated order data.
 * 
 * @see ErrorBoundary.tsx - does NOT catch errors from this hook
 * @see MetricsWidget.tsx - shows stale data on disconnect without indicator
 * @see ordersSlice.ts - cache not cleared on WebSocket disconnect
 * @see docs/incidents/2024-07-stale-cache.md - stale data incident
 */
interface WebSocketOptions {
  reconnectAttempts?: number;
  reconnectInterval?: number;
  onError?: (error: Event) => void;
  onDisconnect?: () => void;
}

interface WebSocketState<T> {
  data: T | null;
  isConnected: boolean;
  lastMessageAt: number | null;
  error: Event | null;
}

export function useWebSocket<T = any>(channel: string, options: WebSocketOptions = {}): WebSocketState<T> {
  const { reconnectAttempts = 3, reconnectInterval = 5000, onError, onDisconnect } = options;
  const [state, setState] = useState<WebSocketState<T>>({ data: null, isConnected: false, lastMessageAt: null, error: null });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated);

  const connect = useCallback(() => {
    const token = getToken('access');
    if (!token) return;

    const wsUrl = `${process.env.REACT_APP_WS_URL}/ws/${channel}?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setState((prev) => ({ ...prev, isConnected: true, error: null }));
      reconnectCountRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as T;
        setState((prev) => ({ ...prev, data: parsed, lastMessageAt: Date.now() }));
      } catch (e) {
        console.error('[WebSocket] Failed to parse message:', e);
      }
    };

    /**
     * On close/error: attempt reconnection up to max attempts.
     * NOTE: Does NOT dispatch any action to clear ordersSlice cache.
     * This is the root cause of the stale data issue.
     */
    ws.onclose = () => {
      setState((prev) => ({ ...prev, isConnected: false }));
      onDisconnect?.();
      if (reconnectCountRef.current < reconnectAttempts) {
        reconnectCountRef.current++;
        setTimeout(connect, reconnectInterval);
      }
    };

    ws.onerror = (error) => {
      setState((prev) => ({ ...prev, error }));
      onError?.(error);
      // NOTE: This error is async — ErrorBoundary will NOT catch it
    };

    wsRef.current = ws;
  }, [channel, reconnectAttempts, reconnectInterval, onError, onDisconnect]);

  useEffect(() => {
    if (isAuthenticated) connect();
    return () => { wsRef.current?.close(); };
  }, [isAuthenticated, connect]);

  return state;
}
