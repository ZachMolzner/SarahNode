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
  conversation_mode?: "personal" | "shared";
};

export type AssistantStateResponse = {
  assistant_state: string;
  latest_reply: string;
  memory_summary: string;
  providers?: {
    llm?: { active?: string; mode?: string };
    tts?: { active?: string; mode?: string };
  };
};

export async function sendAssistantMessage(payload: SendAssistantMessagePayload): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/assistant/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, priority: payload.priority ?? 1, conversation_mode: payload.conversation_mode ?? "personal" }),
  });

  if (!response.ok) {
    throw new Error(`Failed to queue message: ${response.status}`);
  }
}

export type IdentityProfile = {
  id: string;
  display_name?: string;
  preferred_address?: string;
  alternate_addresses?: string[];
  tone_preference?: string;
  response_style?: string;
  voice_profile_id?: string | null;
  members?: string[];
};

export type IdentityStateResponse = {
  profiles: IdentityProfile[];
  shared_profiles: IdentityProfile[];
  explicit_identity_facts: Array<{ id: string; scope: string; key: string; value: string; source: string }>;
  nickname_policy: { aleena_mama_enabled: boolean; aleena_mama_usage_ratio: number };
  speaker: { high_confidence_threshold: number; unknown_fallback: string };
};

export type MemoryItem = {
  id: string;
  scope: "zach" | "aleena" | "household";
  category: "identity" | "preference" | "habit" | "routine";
  source: "explicit" | "inferred";
  key: string;
  value: string;
  confidence: number;
  sensitive: boolean;
};

export async function fetchIdentityState(): Promise<IdentityStateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/assistant/identity`);
  if (!response.ok) throw new Error(`Failed to fetch identity state: ${response.status}`);
  return (await response.json()) as IdentityStateResponse;
}

export async function updateNicknamePolicy(enabled: boolean, usageRatio?: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/assistant/identity/nickname-policy`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled, usage_ratio: usageRatio }),
  });
  if (!response.ok) throw new Error(`Failed to update nickname policy: ${response.status}`);
}

export async function updateProfile(profileId: string, patch: Partial<IdentityProfile>): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/assistant/identity/profiles/${profileId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(`Failed to update profile: ${response.status}`);
}

export async function fetchMemoryItems(scope?: string): Promise<MemoryItem[]> {
  const url = new URL(`${API_BASE_URL}/api/assistant/memory`);
  if (scope) url.searchParams.set("scope", scope);
  const response = await fetch(url.toString());
  if (!response.ok) throw new Error(`Failed to fetch memory items: ${response.status}`);
  const payload = (await response.json()) as { items: MemoryItem[] };
  return payload.items;
}

export async function deleteMemoryItem(itemId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/assistant/memory/${itemId}`, { method: "DELETE" });
  if (!response.ok) throw new Error(`Failed to delete memory item: ${response.status}`);
}

export async function resetVoiceProfile(profileId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/assistant/voice/reset/${profileId}`, { method: "POST" });
  if (!response.ok) throw new Error(`Failed to reset voice profile: ${response.status}`);
}

export async function fetchAssistantState(): Promise<AssistantStateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/assistant/state`);
  if (!response.ok) {
    throw new Error(`Failed to fetch assistant state: ${response.status}`);
  }
  return (await response.json()) as AssistantStateResponse;
}



export async function emitVoiceEvent(eventType: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/assistant/voice/event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_type: eventType }),
  });

  if (!response.ok) {
    throw new Error(`Failed to emit voice event: ${response.status}`);
  }
}

export type TranscriptionResponse = {
  text: string;
  provider: {
    name?: string;
    model?: string;
    mime_type?: string | null;
  };
  duration_ms: number;
};

export async function transcribeAudio(blob: Blob): Promise<TranscriptionResponse> {
  const formData = new FormData();
  formData.append("file", blob, `recording.${blob.type.includes("webm") ? "webm" : "wav"}`);

  const response = await fetch(`${API_BASE_URL}/api/assistant/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let detail = `Transcription failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // no-op
    }
    throw new Error(detail);
  }

  return (await response.json()) as TranscriptionResponse;
}
export function getWsEventsUrl(): string {
  return `${resolveWsBaseUrl()}/ws/events`;
}
