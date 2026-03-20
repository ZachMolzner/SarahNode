export const EVENT_STREAM_LIMITS = {
  maxBufferedEvents: 250,
  heartbeatIntervalMs: 20_000,
  reconnectStepMs: 750,
  reconnectMaxDelayMs: 3_000,
} as const;
