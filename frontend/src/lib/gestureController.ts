import type { AvatarMode, AvatarMood } from "../types/avatar";

export type GestureTone = "warm" | "cheerful" | "focused" | "calm" | "apologetic" | "goodbye";

export type GestureName =
  | "none"
  | "startup_greeting"
  | "shutdown_goodbye"
  | "listening_ack"
  | "response_delivery"
  | "thinking_focus"
  | "idle_micro"
  | "idle_reset";

type GestureDefinition = {
  priority: number;
  durationMs: number;
  cooldownMs: number;
  interruptible: boolean;
};

export type GestureUpdateInput = {
  nowMs: number;
  mode: AvatarMode;
  mood: AvatarMood;
  isSpeaking: boolean;
  startupRequested: boolean;
  shutdownRequested: boolean;
  listeningStartedAtMs: number;
  replyStartedAtMs: number;
  speakingStartedAtMs: number;
  latestReplyText: string;
};

export type GesturePerformanceSnapshot = {
  activeGesture: GestureName;
  tone: GestureTone;
  priority: number;
  progress: number;
  bodyLean: number;
  headTilt: number;
  headNod: number;
  postureOpen: number;
  shoulderSettle: number;
  bobAccent: number;
  bowDepth: number;
  glowBoost: number;
  expressionSoftness: number;
  emphasisPulse: number;
  isRecovering: boolean;
};

const DEFINITIONS: Record<Exclude<GestureName, "none">, GestureDefinition> = {
  startup_greeting: { priority: 1, durationMs: 2800, cooldownMs: 99999999, interruptible: false },
  shutdown_goodbye: { priority: 2, durationMs: 2800, cooldownMs: 99999999, interruptible: false },
  listening_ack: { priority: 3, durationMs: 920, cooldownMs: 2600, interruptible: true },
  response_delivery: { priority: 4, durationMs: 1600, cooldownMs: 1800, interruptible: true },
  thinking_focus: { priority: 5, durationMs: 1600, cooldownMs: 0, interruptible: true },
  idle_micro: { priority: 6, durationMs: 1300, cooldownMs: 6800, interruptible: true },
  idle_reset: { priority: 7, durationMs: 760, cooldownMs: 0, interruptible: true },
};

function clamp01(value: number) {
  return Math.min(1, Math.max(0, value));
}

function resolveGestureTone(mode: AvatarMode, mood: AvatarMood, latestReplyText: string, gesture: GestureName): GestureTone {
  if (gesture === "shutdown_goodbye" || mood === "goodbye" || mode === "shutting_down") return "goodbye";
  if (gesture === "startup_greeting") return "cheerful";
  if (mode === "thinking" || mood === "thinking" || mood === "focused") return "focused";

  const text = latestReplyText.toLowerCase();
  if (/sorry|apolog/i.test(text)) return "apologetic";
  if (/great|excited|happy|awesome|glad/.test(text)) return "cheerful";
  if (/step|plan|because|first|next|then/.test(text)) return "focused";

  if (mode === "listening") return "calm";
  return "warm";
}

export class GestureController {
  private activeGesture: GestureName = "none";
  private activeStartMs = 0;
  private cooldowns: Partial<Record<GestureName, number>> = {};
  private startupConsumed = false;
  private shutdownConsumed = false;
  private recoveryUntilMs = 0;
  private lastListeningAt = 0;
  private lastReplyAt = 0;
  private lastSpeakingAt = 0;
  private idlePulseAt = 0;

  update(input: GestureUpdateInput): GesturePerformanceSnapshot {
    if (input.startupRequested && !this.startupConsumed) {
      this.tryStart("startup_greeting", input.nowMs, true);
      this.startupConsumed = this.activeGesture === "startup_greeting";
    }

    if (input.shutdownRequested && !this.shutdownConsumed) {
      this.tryStart("shutdown_goodbye", input.nowMs, true);
      this.shutdownConsumed = this.activeGesture === "shutdown_goodbye";
    }

    if (input.listeningStartedAtMs > this.lastListeningAt) {
      this.lastListeningAt = input.listeningStartedAtMs;
      this.tryStart("listening_ack", input.nowMs);
    }

    const responseTriggerAt = Math.max(input.replyStartedAtMs, input.speakingStartedAtMs);
    if (responseTriggerAt > this.lastReplyAt && input.mode !== "shutting_down") {
      this.lastReplyAt = responseTriggerAt;
      this.tryStart("response_delivery", input.nowMs);
    }

    if (input.speakingStartedAtMs > this.lastSpeakingAt) {
      this.lastSpeakingAt = input.speakingStartedAtMs;
    }

    const activeDefinition = this.activeGesture === "none" ? null : DEFINITIONS[this.activeGesture];
    if (activeDefinition && input.nowMs - this.activeStartMs >= activeDefinition.durationMs) {
      this.activeGesture = "none";
      this.recoveryUntilMs = input.nowMs + DEFINITIONS.idle_reset.durationMs;
    }

    if (this.activeGesture === "none") {
      if (input.mode === "thinking") {
        this.tryStart("thinking_focus", input.nowMs, true);
      } else if (input.mode === "idle" && input.nowMs - this.idlePulseAt > DEFINITIONS.idle_micro.cooldownMs) {
        this.idlePulseAt = input.nowMs;
        this.tryStart("idle_micro", input.nowMs);
      }
    }

    const progress = this.resolveProgress(input.nowMs);
    const isRecovering = this.activeGesture === "none" && this.recoveryUntilMs > input.nowMs;
    const tone = resolveGestureTone(input.mode, input.mood, input.latestReplyText, this.activeGesture);

    return this.composeSnapshot(this.activeGesture, tone, progress, isRecovering);
  }

  private resolveProgress(nowMs: number): number {
    if (this.activeGesture === "none") return 0;
    const def = DEFINITIONS[this.activeGesture];
    return clamp01((nowMs - this.activeStartMs) / def.durationMs);
  }

  private tryStart(gesture: Exclude<GestureName, "none">, nowMs: number, force = false) {
    const definition = DEFINITIONS[gesture];
    const cooldownUntil = this.cooldowns[gesture] ?? 0;
    if (!force && nowMs < cooldownUntil) return;

    if (this.activeGesture === "none") {
      this.startGesture(gesture, nowMs, definition);
      return;
    }

    const currentDefinition = DEFINITIONS[this.activeGesture];
    const canInterrupt = definition.priority < currentDefinition.priority || currentDefinition.interruptible;

    if (force || canInterrupt) {
      this.startGesture(gesture, nowMs, definition);
    }
  }

  private startGesture(gesture: Exclude<GestureName, "none">, nowMs: number, definition: GestureDefinition) {
    this.activeGesture = gesture;
    this.activeStartMs = nowMs;
    this.cooldowns[gesture] = nowMs + definition.cooldownMs;
  }

  private composeSnapshot(
    gesture: GestureName,
    tone: GestureTone,
    progress: number,
    isRecovering: boolean
  ): GesturePerformanceSnapshot {
    const inPulse = Math.sin(progress * Math.PI);
    const introPulse = Math.max(0, 1 - progress * 2.2);

    const toneOpen = tone === "cheerful" ? 0.32 : tone === "focused" ? 0.08 : tone === "goodbye" ? 0.12 : 0.18;
    const toneTilt = tone === "apologetic" ? -0.045 : tone === "focused" ? -0.018 : 0.02;

    const base: GesturePerformanceSnapshot = {
      activeGesture: gesture,
      tone,
      priority: gesture === "none" ? 99 : DEFINITIONS[gesture].priority,
      progress,
      bodyLean: tone === "focused" ? -0.03 : 0,
      headTilt: toneTilt,
      headNod: 0,
      postureOpen: toneOpen,
      shoulderSettle: 0.02,
      bobAccent: 0,
      bowDepth: 0,
      glowBoost: tone === "cheerful" ? 0.16 : 0.08,
      expressionSoftness: tone === "goodbye" ? 0.2 : 0.12,
      emphasisPulse: 0,
      isRecovering,
    };

    if (gesture === "startup_greeting") {
      base.bodyLean = 0.055 * inPulse;
      base.headTilt = 0.045 + Math.sin(progress * Math.PI * 2) * 0.03;
      base.postureOpen = 0.38;
      base.bobAccent = 0.18 * inPulse;
      base.glowBoost = 0.24;
      base.emphasisPulse = introPulse;
    } else if (gesture === "shutdown_goodbye") {
      const bowDrive = progress < 0.62 ? progress / 0.62 : (1 - progress) / 0.38;
      base.bodyLean = -0.045;
      base.headTilt = -0.02;
      base.bowDepth = Math.max(0, bowDrive) * 0.4;
      base.postureOpen = 0.08;
      base.shoulderSettle = 0.15;
      base.glowBoost = 0.06;
      base.expressionSoftness = 0.28;
    } else if (gesture === "listening_ack") {
      base.bodyLean = 0.07 * inPulse;
      base.headTilt = 0.07 * inPulse;
      base.headNod = 0.05 * inPulse;
      base.postureOpen = 0.17;
      base.bobAccent = 0.08 * inPulse;
    } else if (gesture === "response_delivery") {
      base.bodyLean = 0.04;
      base.headTilt = 0.02 + Math.sin(progress * Math.PI * 2.4) * 0.015;
      base.headNod = 0.028 * inPulse;
      base.postureOpen = toneOpen + 0.08;
      base.emphasisPulse = introPulse;
      base.bobAccent = 0.07;
      base.glowBoost = 0.14;
    } else if (gesture === "thinking_focus") {
      base.bodyLean = -0.05;
      base.headTilt = -0.05;
      base.postureOpen = 0.05;
      base.bobAccent = -0.05;
      base.glowBoost = 0.04;
    } else if (gesture === "idle_micro") {
      base.bodyLean = 0.02 * inPulse;
      base.headTilt = 0.01 * Math.sin(progress * Math.PI * 2);
      base.postureOpen = 0.12;
      base.bobAccent = 0.03;
    }

    if (isRecovering) {
      base.bodyLean *= 0.4;
      base.headTilt *= 0.4;
      base.headNod *= 0.4;
      base.bowDepth *= 0.4;
      base.postureOpen *= 0.7;
      base.bobAccent *= 0.4;
      base.glowBoost *= 0.7;
      base.emphasisPulse *= 0.4;
    }

    return base;
  }
}
