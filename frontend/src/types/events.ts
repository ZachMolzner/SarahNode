export type SystemEvent = {
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
};
