export type KnownEventType =
  | "chat_received"
  | "moderation_decision"
  | "assistant_state"
  | "reply_selected"
  | "web_grounded_answer"
  | "speaking_status"
  | "tts_output"
  | "avatar_event"
  | "voice:recording_started"
  | "voice:recording_stopped"
  | "voice:transcribing"
  | "voice:transcribed"
  | "voice:error"
  | "error";

export type EventPayload = Record<string, unknown>;

export type AssistantStatePayload = EventPayload & {
  state?: string;
};

export type ReplySelectedPayload = EventPayload & {
  text?: string;
  emotion?: string;
};

export type SpeakingStatusPayload = EventPayload & {
  is_speaking?: boolean;
};

export type KnownPayloadByEvent = {
  chat_received: EventPayload;
  moderation_decision: EventPayload;
  assistant_state: AssistantStatePayload;
  reply_selected: ReplySelectedPayload;
  web_grounded_answer: EventPayload;
  speaking_status: SpeakingStatusPayload;
  tts_output: EventPayload;
  avatar_event: EventPayload;
  "voice:recording_started": EventPayload;
  "voice:recording_stopped": EventPayload;
  "voice:transcribing": EventPayload;
  "voice:transcribed": EventPayload;
  "voice:error": EventPayload;
  error: EventPayload;
};

export type KnownSystemEvent = {
  [T in KnownEventType]: {
    type: T;
    timestamp: string;
    payload: KnownPayloadByEvent[T];
  };
}[KnownEventType];

export type UnknownSystemEvent = {
  type: string;
  timestamp: string;
  payload: EventPayload;
};

export type SystemEvent = KnownSystemEvent | UnknownSystemEvent;

export type ConnectionState = "connecting" | "open" | "closed" | "error";

const KNOWN_EVENT_TYPES: ReadonlySet<KnownEventType> = new Set([
  "chat_received",
  "moderation_decision",
  "assistant_state",
  "reply_selected",
  "web_grounded_answer",
  "speaking_status",
  "tts_output",
  "avatar_event",
  "voice:recording_started",
  "voice:recording_stopped",
  "voice:transcribing",
  "voice:transcribed",
  "voice:error",
  "error",
]);

export function isKnownEventType(type: string): type is KnownEventType {
  return KNOWN_EVENT_TYPES.has(type as KnownEventType);
}

export function findLatestKnownEvent<T extends KnownEventType>(
  events: SystemEvent[],
  type: T
): Extract<KnownSystemEvent, { type: T }> | undefined {
  return events.find((event): event is Extract<KnownSystemEvent, { type: T }> => event.type === type);
}
