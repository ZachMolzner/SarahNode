export type AvatarMood = "neutral" | "warm" | "listening" | "curious" | "thinking" | "cheerful" | "focused" | "goodbye";

export type AvatarExpression =
  | "neutral"
  | "warm"
  | "attentive"
  | "curious"
  | "focused"
  | "presenting"
  | "surprised"
  | "apologetic";

export type AvatarReaction = "summoned_perk" | "interaction_start" | "grounded_result" | "source_expanded" | "interrupted" | "error" | "none";

export type AvatarMode = "idle" | "walking" | "listening" | "thinking" | "talking" | "presenting" | "shutting_down";

export type AvatarState = {
  mode: AvatarMode;
  mood: AvatarMood;
  isSpeaking: boolean;
  mouthIntensity?: number;
  expression?: AvatarExpression;
  reaction?: AvatarReaction;
  expressionIntensity?: number;
};

export const DEFAULT_AVATAR_STATE: AvatarState = {
  mode: "idle",
  mood: "neutral",
  isSpeaking: false,
  mouthIntensity: 0,
  expression: "neutral",
  reaction: "none",
  expressionIntensity: 1,
};
