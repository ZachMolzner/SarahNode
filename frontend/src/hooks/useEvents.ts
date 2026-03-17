import { useEffect, useMemo, useRef, useState } from "react";
import { getWsEventsUrl } from "../lib/api";
import type { ConnectionState, SystemEvent } from "../types/events";

type UseEventsResult = {
  events: SystemEvent[];
  connectionState: ConnectionState;
};

const MAX_EVENTS = 250;

function parseEvent(raw: string): SystemEvent | null {
  try {
    const parsed = JSON.parse(raw) as Partial<SystemEvent>;
    if (!parsed || typeof parsed.type !== "string" || typeof parsed.timestamp !== "string") {
      return null;
    }

    return {
      type: parsed.type,
      timestamp: parsed.timestamp,
      payload: typeof parsed.payload === "object" && parsed.payload !== null ? parsed.payload : {},
    };
  } catch {
    return null;
  }
}

export function useEvents(url = getWsEventsUrl()): UseEventsResult {
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");

  const retriesRef = useRef(0);
  const timeoutRef = useRef<number | null>(null);
  const heartbeatRef = useRef<number | null>(null);

  useEffect(() => {
    let mounted = true;
    let socket: WebSocket | null = null;

    const clearTimers = () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }

      if (heartbeatRef.current !== null) {
        window.clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
    };

    const connect = () => {
      if (!mounted) return;

      setConnectionState("connecting");
      socket = new WebSocket(url);

      socket.onopen = () => {
        if (!mounted || !socket) return;
        retriesRef.current = 0;
        setConnectionState("open");

        heartbeatRef.current = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send("ping");
          }
        }, 20000);
      };

      socket.onmessage = (message) => {
        if (!mounted) return;
        const parsed = parseEvent(message.data);
        if (!parsed) return;
        setEvents((current) => [parsed, ...current].slice(0, MAX_EVENTS));
      };

      socket.onerror = () => {
        if (!mounted) return;
        setConnectionState("error");
      };

      socket.onclose = () => {
        if (!mounted) return;

        clearTimers();
        setConnectionState("closed");
        retriesRef.current += 1;

        const reconnectDelay = Math.min(3000, retriesRef.current * 750);
        timeoutRef.current = window.setTimeout(connect, reconnectDelay);
      };
    };

    connect();

    return () => {
      mounted = false;
      clearTimers();
      socket?.close();
    };
  }, [url]);

  return useMemo(
    () => ({
      events,
      connectionState,
    }),
    [events, connectionState]
  );
}
