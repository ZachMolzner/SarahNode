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
  summoned_perk: 1050,
  interaction_start: 760,
  grounded_result: 1450,
  source_expanded: 900,
  interrupted: 820,
  error: 1600,
} as const;

const SEARCH_FOCUS_HOLD_MS = 1200;
const SPEAKING_SETTLE_MS = 1200;
const INTERRUPTION_RECOVERY_MS = 1400;
const ERROR_RECOVERY_MS = 1750;
const SOURCE_ACK_PULSE_MS = 520;

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

  if (isRecent(input.nowMs, input.searchStartedAtMs, SEARCH_FOCUS_HOLD_MS)) {
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

  const sinceSpeakingEnded = input.speakingEndedAtMs > 0 ? input.nowMs - input.speakingEndedAtMs : Number.POSITIVE_INFINITY;
  const withinSpeakingSettle = !input.isSpeaking && sinceSpeakingEnded >= 0 && sinceSpeakingEnded < SPEAKING_SETTLE_MS;
  if (withinSpeakingSettle) {
    expression = "attentive";
  }

  const withinInterruptionRecovery =
    input.interruptedAtMs > 0 &&
    input.nowMs - input.interruptedAtMs > REACTION_MS.interrupted &&
    input.nowMs - input.interruptedAtMs <= INTERRUPTION_RECOVERY_MS &&
    !input.isSpeaking;

  const withinErrorRecovery =
    (input.errorAtMs > 0 && input.nowMs - input.errorAtMs > REACTION_MS.error && input.nowMs - input.errorAtMs <= ERROR_RECOVERY_MS) ||
    (input.noResultAtMs > 0 &&
      input.nowMs - input.noResultAtMs > REACTION_MS.error &&
      input.nowMs - input.noResultAtMs <= ERROR_RECOVERY_MS);

  if ((withinInterruptionRecovery || withinErrorRecovery) && !input.isPresenting) {
    expression = "attentive";
  }

  const sourcePulseBoost = isRecent(input.nowMs, input.sourceExpandedAtMs, SOURCE_ACK_PULSE_MS) ? 0.03 : 0;
  const overlayBase = input.isOverlayMode ? 0.69 : 0.85;
  const immersiveBoost = input.isOverlayMode ? 0 : 0.06;
  const reactionBoost =
    reaction === "none"
      ? 0
      : reaction === "interrupted"
        ? 0.11
        : reaction === "error"
          ? 0.08
          : reaction === "grounded_result"
            ? 0.06
            : 0.045;
  const modeExpressionBias = input.isOverlayMode && (expression === "surprised" || expression === "apologetic") ? -0.02 : 0;
  const settleReduction = withinSpeakingSettle || withinInterruptionRecovery || withinErrorRecovery ? -0.04 : 0;
  const intensity = Math.min(1, Math.max(0.56, overlayBase + immersiveBoost + reactionBoost + sourcePulseBoost + modeExpressionBias + settleReduction));

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
