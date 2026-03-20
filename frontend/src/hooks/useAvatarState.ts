import { useMemo } from "react";
import { findLatestKnownEvent, type SystemEvent } from "../types/events";
import { type AvatarMood, type AvatarState } from "../types/avatar";

function moodFromEmotion(emotion: unknown): AvatarMood {
  if (typeof emotion !== "string") return "warm";

  const normalized = emotion.toLowerCase();
  if (["happy", "joy", "excited", "positive"].includes(normalized)) return "cheerful";
  if (["curious", "wonder", "interested"].includes(normalized)) return "curious";
  if (["calm", "gentle", "relaxed", "peaceful"].includes(normalized)) return "warm";
  if (["serious", "focused"].includes(normalized)) return "focused";
  return "neutral";
}

export function useAvatarState(events: SystemEvent[]): AvatarState {
  return useMemo(() => {
    const assistantStateEvent = findLatestKnownEvent(events, "assistant_state");
    const replySelectedEvent = findLatestKnownEvent(events, "reply_selected");
    const speakingStatusEvent = findLatestKnownEvent(events, "speaking_status");
    const latestVoiceEvent = events.find((event) => event.type.startsWith("voice:"));

    const isSpeaking = speakingStatusEvent?.payload.is_speaking === true;
    const assistantState = assistantStateEvent?.payload.state;
    const replyEmotion = replySelectedEvent?.payload.emotion;

    const mode =
      isSpeaking
        ? "talking"
        : latestVoiceEvent?.type === "voice:recording_started"
          ? "listening"
          : typeof assistantState === "string" && assistantState.toLowerCase() === "thinking"
            ? "thinking"
            : "idle";

    const mood: AvatarMood =
      mode === "listening"
        ? "listening"
        : mode === "thinking"
          ? "thinking"
          : mode === "talking"
            ? "warm"
            : moodFromEmotion(replyEmotion);

    return {
      mode,
      mood,
      isSpeaking,
      mouthIntensity: isSpeaking ? 0.55 : 0,
    };
  }, [events]);
}
