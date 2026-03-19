export type AvatarMood = "neutral" | "happy" | "concerned" | "calm" | "goodbye";

export type AvatarMode = "idle" | "listening" | "thinking" | "speaking" | "shutting_down";

export type AvatarState = {
  mode: AvatarMode;
  mood: AvatarMood;
  isSpeaking: boolean;
};

export const DEFAULT_AVATAR_STATE: AvatarState = {
  mode: "idle",
  mood: "neutral",
  isSpeaking: false,
};
