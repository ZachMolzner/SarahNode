export type AvatarMood = "neutral" | "happy" | "concerned" | "calm";

export type AvatarMode = "idle" | "listening" | "thinking" | "speaking";

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
