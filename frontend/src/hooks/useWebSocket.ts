import { useEffect, useRef, useState } from "react";
import { buildWsUrl } from "@/api/client";
import type { WsEvent } from "@/types";

/**
 * 通用 WebSocket hook：连接 /api/v1{path}?token=xxx，自动重连
 */
export function useWebSocket<T extends WsEvent = WsEvent>(
  path: string | null,
  onMessage?: (msg: T) => void
) {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!path) return;
    const url = buildWsUrl(path);

    const connect = () => {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        retryRef.current = 0;
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as T;
          setLastMessage(msg);
          onMessage?.(msg);
        } catch {
          // ignore non-json
        }
      };
      ws.onclose = () => {
        setConnected(false);
        // 指数退避重连
        retryRef.current += 1;
        const delay = Math.min(1000 * 2 ** retryRef.current, 30000);
        timerRef.current = window.setTimeout(connect, delay);
      };
      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  const send = (data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  };

  return { connected, lastMessage, send };
}
