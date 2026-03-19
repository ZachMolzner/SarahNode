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
  listeningStartedAtMs: number;
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
  debug: {
    baseline: AvatarExpression;
    interruptionGateActive: boolean;
    speakingSettleActive: boolean;
    errorRecoveryActive: boolean;
  };
};

const REACTION_MS = {
  summoned_perk: 1050,
  interaction_start: 760,
  grounded_result: 1450,
  source_expanded: 900,
  interrupted: 820,
  error: 1600,
  searching: 1400,
  listening_ready: 1100,
  confident_result: 1650,
  uncertain_result: 1500,
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
  if (isRecent(input.nowMs, input.interruptedAtMs, REACTION_MS.interrupted)) {
    return "interrupted";
  }

  if (input.interruptedAtMs > 0 && input.nowMs - input.interruptedAtMs <= INTERRUPTION_RECOVERY_MS) {
    return "none";
  }

  if (isRecent(input.nowMs, input.errorAtMs, REACTION_MS.error)) {
    return "error";
  }

  if (isRecent(input.nowMs, input.noResultAtMs, REACTION_MS.uncertain_result)) {
    return "uncertain_result";
  }

  if (isRecent(input.nowMs, input.groundedAnswerAtMs, REACTION_MS.confident_result)) {
    return "confident_result";
  }

  if (isRecent(input.nowMs, input.searchStartedAtMs, SEARCH_FOCUS_HOLD_MS)) {
    return "searching";
  }

  if (
    isRecent(input.nowMs, input.listeningStartedAtMs, REACTION_MS.listening_ready) &&
    !input.isThinking &&
    !input.isSpeaking &&
    input.mode === "listening"
  ) {
    return "listening_ready";
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
  const interruptionGateActive = input.interruptedAtMs > 0 && input.nowMs - input.interruptedAtMs <= INTERRUPTION_RECOVERY_MS;
  const reaction = reactionFromInput(input);

  let expression = baseline;
  if (reaction === "error") expression = "apologetic";
  if (reaction === "uncertain_result") expression = "attentive";
  if (reaction === "interrupted") expression = "surprised";
  if (reaction === "summoned_perk") expression = "warm";
  if (reaction === "interaction_start" && baseline !== "presenting" && !input.isSpeaking) expression = "curious";
  if (reaction === "searching" && !input.isSpeaking && !input.isPresenting) expression = "curious";
  if (reaction === "listening_ready" && !input.isSpeaking && !input.isPresenting) {
    const earlyListeningReady = input.nowMs - input.listeningStartedAtMs < 420;
    expression = earlyListeningReady ? "curious" : "attentive";
  }
  if (reaction === "confident_result") expression = "presenting";
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

  if (withinInterruptionRecovery || withinErrorRecovery) {
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
          : reaction === "uncertain_result"
            ? 0.05
            : reaction === "confident_result" || reaction === "grounded_result"
            ? 0.06
            : reaction === "searching"
              ? 0.035
              : reaction === "listening_ready"
                ? 0.02
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

  return {
    expression,
    mood,
    reaction,
    intensity,
    debug: {
      baseline,
      interruptionGateActive,
      speakingSettleActive: withinSpeakingSettle,
      errorRecoveryActive: withinErrorRecovery,
    },
  };
}
