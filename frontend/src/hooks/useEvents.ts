import { useEffect, useMemo, useRef, useState } from "react";
import type { ConnectionState, SystemEvent } from "../types/events";

type UseEventsResult = {
  events: SystemEvent[];
  connectionState: ConnectionState;
};

const MAX_EVENTS = 200;

function parseEvent(raw: string): SystemEvent | null {
  try {
    const parsed = JSON.parse(raw) as Partial<SystemEvent>;

    if (!parsed || typeof parsed.type !== "string" || typeof parsed.timestamp !== "string") {
      return null;
    }

    return {
      type: parsed.type,
      timestamp: parsed.timestamp,
      payload:
        typeof parsed.payload === "object" && parsed.payload !== null ? parsed.payload : {},
    };
  } catch {
    return null;
  }
}

export function useEvents(url = "ws://localhost:8000/ws/events"): UseEventsResult {
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");

  const retriesRef = useRef(0);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    let mounted = true;
    let socket: WebSocket | null = null;

    const connect = () => {
      if (!mounted) return;

      setConnectionState("connecting");
      socket = new WebSocket(url);

      socket.onopen = () => {
        if (!mounted) return;
        retriesRef.current = 0;
        setConnectionState("open");
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

        setConnectionState("closed");
        retriesRef.current += 1;

        const reconnectDelay = Math.min(3000, retriesRef.current * 750);
        timeoutRef.current = window.setTimeout(connect, reconnectDelay);
      };
    };

    connect();

    return () => {
      mounted = false;

      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }

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
