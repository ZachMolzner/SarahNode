export type EventType =
  | 'chat_received'
  | 'moderation_decision'
  | 'reply_selected'
  | 'speaking_status'
  | 'tts_output'
  | 'avatar_event'
  | 'error';

export type SystemEvent = {
  type: EventType | string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export type ConnectionState = 'connecting' | 'open' | 'closed' | 'error';
