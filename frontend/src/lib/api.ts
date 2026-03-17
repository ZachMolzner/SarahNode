function normalizeBaseUrl(raw: string): string {
  return raw.replace(/\/+$/, "");
}

function resolveApiBaseUrl(): string {
  const envBase = import.meta.env.VITE_PUBLIC_API_BASE_URL?.trim();
  if (envBase) {
    return normalizeBaseUrl(envBase);
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "https" : "http";
    return `${protocol}://${window.location.hostname}:8000`;
  }

  return "http://127.0.0.1:8000";
}

function resolveWsBaseUrl(): string {
  const envBase = import.meta.env.VITE_PUBLIC_WS_BASE_URL?.trim();
  if (envBase) {
    return normalizeBaseUrl(envBase);
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    return `${protocol}://${window.location.hostname}:8000`;
  }

  return "ws://127.0.0.1:8000";
}

const API_BASE_URL = resolveApiBaseUrl();

export type SendAssistantMessagePayload = {
  username: string;
  content: string;
  priority?: number;
};

export async function sendAssistantMessage(payload: SendAssistantMessagePayload): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/assistant/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, priority: payload.priority ?? 1 }),
  });

  if (!response.ok) {
    throw new Error(`Failed to queue message: ${response.status}`);
  }
}

export function getWsEventsUrl(): string {
  return `${resolveWsBaseUrl()}/ws/events`;
}
