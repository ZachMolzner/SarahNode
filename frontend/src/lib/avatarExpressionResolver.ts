import type { AvatarExpression, AvatarMode, AvatarMood, AvatarReaction } from "../types/avatar";

export type ExpressionResolverInput = {
  nowMs: number;
  mode: AvatarMode;
  isSpeaking: boolean;
  isPresenting: boolean;
  isThinking: boolean;
  isListening: boolean;
  isOverlayMode: boolean;
  isInteracting: boolean;
  recentlyActiveMs: number;
  summonedAtMs: number;
  interactionStartedAtMs: number;
  searchStartedAtMs: number;
  groundedAnswerAtMs: number;
  sourceExpandedAtMs: number;
  interruptedAtMs: number;
  errorAtMs: number;
  noResultAtMs: number;
  speakingEndedAtMs: number;
};

export type ExpressionResolverOutput = {
  expression: AvatarExpression;
  mood: AvatarMood;
  reaction: AvatarReaction;
  intensity: number;
};

const REACTION_MS = {
  summoned_perk: 1400,
  interaction_start: 900,
  grounded_result: 1800,
  source_expanded: 1500,
  interrupted: 1100,
  error: 1900,
} as const;

function isRecent(nowMs: number, atMs: number, windowMs: number) {
  return atMs > 0 && nowMs - atMs >= 0 && nowMs - atMs <= windowMs;
}

function baselineExpression(input: ExpressionResolverInput): AvatarExpression {
  if (input.isSpeaking || input.mode === "talking") return "warm";
  if (input.isPresenting || input.mode === "presenting") return "presenting";
  if (input.isThinking || input.mode === "thinking") return "focused";
  if (input.isListening || input.mode === "listening") return "attentive";
  if (input.recentlyActiveMs < 12000 || input.isInteracting) return "attentive";
  return "neutral";
}

function reactionFromInput(input: ExpressionResolverInput): AvatarReaction {
  if (isRecent(input.nowMs, input.errorAtMs, REACTION_MS.error) || isRecent(input.nowMs, input.noResultAtMs, REACTION_MS.error)) {
    return "error";
  }

  if (isRecent(input.nowMs, input.interruptedAtMs, REACTION_MS.interrupted)) {
    return "interrupted";
  }

  if (isRecent(input.nowMs, input.groundedAnswerAtMs, REACTION_MS.grounded_result)) {
    return "grounded_result";
  }

  if (isRecent(input.nowMs, input.searchStartedAtMs, 1800)) {
    return "interaction_start";
  }

  if (isRecent(input.nowMs, input.sourceExpandedAtMs, REACTION_MS.source_expanded)) {
    return "source_expanded";
  }

  if (isRecent(input.nowMs, input.summonedAtMs, REACTION_MS.summoned_perk)) {
    return "summoned_perk";
  }

  if (isRecent(input.nowMs, input.interactionStartedAtMs, REACTION_MS.interaction_start)) {
    return "interaction_start";
  }

  return "none";
}

export function resolveAvatarExpression(input: ExpressionResolverInput): ExpressionResolverOutput {
  const baseline = baselineExpression(input);
  const reaction = reactionFromInput(input);

  let expression = baseline;
  if (reaction === "error") expression = "apologetic";
  if (reaction === "interrupted") expression = "surprised";
  if (reaction === "summoned_perk") expression = "warm";
  if (reaction === "interaction_start" && baseline !== "presenting" && !input.isSpeaking) expression = "curious";
  if (reaction === "grounded_result") expression = "presenting";
  if (reaction === "source_expanded") expression = "focused";

  if (input.speakingEndedAtMs > 0 && input.nowMs - input.speakingEndedAtMs < 900 && !input.isSpeaking) {
    expression = "attentive";
  }

  const intensityBase = input.isOverlayMode ? 0.78 : 1;
  const intensityBoost =
    reaction === "none" ? 0 : reaction === "error" ? 0.18 : reaction === "interrupted" ? 0.22 : 0.12;
  const intensity = Math.min(1, intensityBase + intensityBoost);

  const mood: AvatarMood =
    expression === "warm"
      ? "warm"
      : expression === "curious"
        ? "curious"
        : expression === "focused" || expression === "presenting"
          ? "focused"
          : expression === "attentive"
            ? "listening"
            : expression === "apologetic"
              ? "neutral"
              : expression === "surprised"
                ? "thinking"
                : "neutral";

  return { expression, mood, reaction, intensity };
}
