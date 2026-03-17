export type EventType =
  | "chat_received"
  | "moderation_decision"
  | "assistant_state"
  | "reply_selected"
  | "tts_output"
  | "avatar_event"
  | "error";

export type EventPayload = Record<string, unknown>;

export type SystemEvent = {
  type: EventType | string;
  timestamp: string;
  payload: EventPayload;
};

export type ConnectionState = "connecting" | "open" | "closed" | "error";
