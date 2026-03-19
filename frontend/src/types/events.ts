export type EventType =
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

export type SystemEvent = {
  type: EventType | string;
  timestamp: string;
  payload: EventPayload;
};

export type ConnectionState = "connecting" | "open" | "closed" | "error";
