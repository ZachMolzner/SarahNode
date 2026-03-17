import { useMemo } from "react";
import type { SystemEvent } from "../types/events";
import { type AvatarMood, type AvatarState } from "../types/avatar";

function moodFromEmotion(emotion: unknown): AvatarMood {
  if (typeof emotion !== "string") return "neutral";

  const normalized = emotion.toLowerCase();
  if (["happy", "joy", "excited", "positive"].includes(normalized)) return "happy";
  if (["concerned", "worried", "sad", "serious"].includes(normalized)) return "concerned";
  if (["calm", "gentle", "relaxed", "peaceful"].includes(normalized)) return "calm";
  return "neutral";
}

function findPayload(events: SystemEvent[], type: string): Record<string, unknown> {
  return events.find((event) => event.type === type)?.payload ?? {};
}

export function useAvatarState(events: SystemEvent[]): AvatarState {
  return useMemo(() => {
    const assistantState = findPayload(events, "assistant_state")["state"];
    const replyEmotion = findPayload(events, "reply_selected")["emotion"];
    const speakingFlag = findPayload(events, "speaking_status")["is_speaking"];

    const isSpeaking = speakingFlag === true;

    const mode =
      isSpeaking
        ? "speaking"
        : typeof assistantState === "string" && assistantState.toLowerCase() === "thinking"
          ? "thinking"
          : "idle";

    return {
      mode,
      mood: moodFromEmotion(replyEmotion),
      isSpeaking,
    };
  }, [events]);
}
