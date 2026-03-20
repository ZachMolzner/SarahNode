import { useEffect, useMemo, useRef, useState } from "react";
import { EVENT_STREAM_LIMITS } from "../config/realtime";
import { getWsEventsUrl } from "../lib/api";
import {
  isKnownEventType,
  type AssistantStatePayload,
  type ConnectionState,
  type EventPayload,
  type KnownEventType,
  type ReplySelectedPayload,
  type SpeakingStatusPayload,
  type SystemEvent,
} from "../types/events";

type UseEventsResult = {
  events: SystemEvent[];
  connectionState: ConnectionState;
};

function toPayloadRecord(rawPayload: unknown): EventPayload {
  return typeof rawPayload === "object" && rawPayload !== null ? (rawPayload as EventPayload) : {};
}

function coerceKnownPayload(type: KnownEventType, payload: EventPayload): EventPayload {
  if (type === "assistant_state") {
    const state = payload["state"];
    return {
      ...payload,
      state: typeof state === "string" ? state : undefined,
    } satisfies AssistantStatePayload;
  }

  if (type === "reply_selected") {
    const text = payload["text"];
    const emotion = payload["emotion"];
    return {
      ...payload,
      text: typeof text === "string" ? text : undefined,
      emotion: typeof emotion === "string" ? emotion : undefined,
    } satisfies ReplySelectedPayload;
  }

  if (type === "speaking_status") {
    const speaking = payload["is_speaking"];
    return {
      ...payload,
      is_speaking: speaking === true,
    } satisfies SpeakingStatusPayload;
  }

  return payload;
}

function parseSystemEventMessage(rawMessage: string): SystemEvent | null {
  try {
    const parsed = JSON.parse(rawMessage) as Partial<SystemEvent>;
    if (!parsed || typeof parsed.type !== "string" || typeof parsed.timestamp !== "string") {
      return null;
    }

    const payload = toPayloadRecord(parsed.payload);

    if (isKnownEventType(parsed.type)) {
      return {
        type: parsed.type,
        timestamp: parsed.timestamp,
        payload: coerceKnownPayload(parsed.type, payload),
      };
    }

    return {
      type: parsed.type,
      timestamp: parsed.timestamp,
      payload,
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
        }, EVENT_STREAM_LIMITS.heartbeatIntervalMs);
      };

      socket.onmessage = (message) => {
        if (!mounted) return;
        const parsed = parseSystemEventMessage(message.data);
        if (!parsed) return;
        setEvents((current) => [parsed, ...current].slice(0, EVENT_STREAM_LIMITS.maxBufferedEvents));
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

        const reconnectDelay = Math.min(
          EVENT_STREAM_LIMITS.reconnectMaxDelayMs,
          retriesRef.current * EVENT_STREAM_LIMITS.reconnectStepMs
        );
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
