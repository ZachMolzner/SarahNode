export type AvatarMood = "neutral" | "warm" | "listening" | "curious" | "thinking" | "cheerful" | "focused" | "goodbye";

export type AvatarMode = "idle" | "walking" | "listening" | "thinking" | "talking" | "presenting" | "shutting_down";

export type AvatarState = {
  mode: AvatarMode;
  mood: AvatarMood;
  isSpeaking: boolean;
  mouthIntensity?: number;
};

export const DEFAULT_AVATAR_STATE: AvatarState = {
  mode: "idle",
  mood: "neutral",
  isSpeaking: false,
  mouthIntensity: 0,
};
