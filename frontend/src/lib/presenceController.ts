import type { MovementState, StagePoint } from "./movementController";
import { resolveStageZones, type OverlayVisibility, type StageBounds, type StageZoneName } from "./stageZones";
import { IdleBehaviorManager } from "./idleBehaviorManager";

export type AttentionTarget = "viewer_center" | "captions_area" | "overlay_area" | "transcript_source" | "web_answer_box" | "idle_neutral" | "inward_focus";

export type PresenceInput = {
  mode: MovementState;
  overlays: OverlayVisibility;
  bounds: StageBounds;
  currentPosition: StagePoint;
  nowMs: number;
  deltaSeconds: number;
  transcriptEventAtMs: number;
  userSpokeAtMs: number;
  replyAtMs: number;
  presentingAtMs: number;
};

export type PresenceOutput = {
  preferredZone: StageZoneName;
  targetPosition: StagePoint;
  attentionTarget: AttentionTarget;
  attentionOffset: StagePoint;
  engagementLevel: number;
  movementWillingness: number;
  activityState: "active" | "idle";
  idleBehavior: "none" | "wander" | "corner_rest";
  poseTiltDeg: number;
  poseYOffset: number;
};

export const PRESENCE_TUNING = {
  minZoneDwellMs: 6400,
  majorMoveCooldownMs: 3600,
  retargetDistanceThreshold: 0.035,
  zoneSwitchDistance: 0.085,
  engagementRisePerSecond: 0.55,
  engagementDecayPerSecond: 0.2,
  transcriptLockMs: 1200,
  postResponseHoldMs: 900,
  recentInteractionMs: 18000,
  idleMicroShiftAmplitude: 0.013,
  focusSmoothing: 0.12,
} as const;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function smooth(current: number, target: number, ratePerSecond: number, deltaSeconds: number) {
  const blend = 1 - Math.exp(-ratePerSecond * Math.max(deltaSeconds, 0.001));
  return current + (target - current) * blend;
}

function distance(a: StagePoint, b: StagePoint) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export class PresenceController {
  private zone: StageZoneName = "right_relaxed";
  private zoneSinceMs = 0;
  private cooldownUntilMs = 0;
  private engagement = 0.3;
  private lastTarget: StagePoint = { x: 0.56, y: 0.58 };
  private focusOffset: StagePoint = { x: 0, y: 0 };
  private idleBehaviorManager = new IdleBehaviorManager();

  update(input: PresenceInput): PresenceOutput {
    const zones = resolveStageZones(input.bounds, input.overlays);
    const desiredZone = this.pickDesiredZone(input);
    const canSwitchZone =
      input.nowMs - this.zoneSinceMs > PRESENCE_TUNING.minZoneDwellMs && input.nowMs > this.cooldownUntilMs;

    if (this.zoneSinceMs === 0) {
      this.zone = desiredZone;
      this.zoneSinceMs = input.nowMs;
      this.lastTarget = zones[this.zone];
    } else if (desiredZone !== this.zone && canSwitchZone) {
      this.zone = desiredZone;
      this.zoneSinceMs = input.nowMs;
      this.cooldownUntilMs = input.nowMs + PRESENCE_TUNING.majorMoveCooldownMs;
    }

    const engagementTarget = this.engagementTarget(input.mode, input);
    const rate = engagementTarget >= this.engagement ? PRESENCE_TUNING.engagementRisePerSecond : PRESENCE_TUNING.engagementDecayPerSecond;
    this.engagement = smooth(this.engagement, engagementTarget, rate, input.deltaSeconds);

    const idleBehavior = this.idleBehaviorManager.update({
      mode: input.mode,
      nowMs: input.nowMs,
      bounds: input.bounds,
      currentPosition: input.currentPosition,
    });

    const baseTarget = idleBehavior.targetPosition ?? zones[this.zone];
    const microOffset = this.idleMicroOffset(input, idleBehavior.idleBehavior);
    const proposedTarget: StagePoint = {
      x: clamp(baseTarget.x + microOffset.x, 0.08, 0.92),
      y: clamp(baseTarget.y + microOffset.y + idleBehavior.poseYOffset, 0.28, 0.82),
    };

    const currentDelta = distance(proposedTarget, this.lastTarget);
    if (currentDelta > PRESENCE_TUNING.retargetDistanceThreshold || distance(input.currentPosition, this.lastTarget) > PRESENCE_TUNING.zoneSwitchDistance) {
      this.lastTarget = proposedTarget;
    }

    const attention = this.resolveAttention(input);
    this.focusOffset.x = smooth(this.focusOffset.x, attention.offset.x, PRESENCE_TUNING.focusSmoothing * 60, input.deltaSeconds);
    this.focusOffset.y = smooth(this.focusOffset.y, attention.offset.y, PRESENCE_TUNING.focusSmoothing * 60, input.deltaSeconds);

    return {
      preferredZone: this.zone,
      targetPosition: this.lastTarget,
      attentionTarget: attention.target,
      attentionOffset: { ...this.focusOffset },
      engagementLevel: this.engagement,
      movementWillingness: idleBehavior.movementWillingness ?? this.movementWillingness(input.mode, input),
      activityState: idleBehavior.activityState,
      idleBehavior: idleBehavior.idleBehavior,
      poseTiltDeg: idleBehavior.poseTiltDeg,
      poseYOffset: idleBehavior.poseYOffset,
    };
  }

  private pickDesiredZone(input: PresenceInput): StageZoneName {
    const transcriptLocked = input.nowMs - input.transcriptEventAtMs < PRESENCE_TUNING.transcriptLockMs;
    if (input.mode === "shutting_down") return "shutdown_settle";
    if (input.mode === "listening") return "listening_anchor";
    if (input.mode === "presenting") return "left_relaxed";
    if (input.mode === "talking") return input.overlays.captionsVisible ? "caption_friendly" : "center_presentation";
    if (input.mode === "thinking") return "center_presentation";
    if (transcriptLocked) return "listening_anchor";

    if (this.engagement > 0.68) return "center_presentation";
    if (this.engagement > 0.45) return "listening_anchor";

    if (input.overlays.controlsOpen && !input.overlays.transcriptOpen) return "left_relaxed";
    if (input.overlays.transcriptOpen && !input.overlays.controlsOpen) return "right_relaxed";

    return Math.sin(input.nowMs / 12000) >= 0 ? "right_relaxed" : "left_relaxed";
  }

  private movementWillingness(mode: MovementState, input: PresenceInput): number {
    if (mode === "shutting_down") return 0;
    if (mode === "presenting") return 0.1;
    if (mode === "talking") return 0.14;
    if (mode === "listening") {
      const transcriptLocked = input.nowMs - input.transcriptEventAtMs < PRESENCE_TUNING.transcriptLockMs;
      return transcriptLocked ? 0.12 : 0.26;
    }
    if (mode === "thinking") return 0.18;
    return 0.34 + this.engagement * 0.22;
  }

  private engagementTarget(mode: MovementState, input: PresenceInput): number {
    if (mode === "shutting_down") return 0;
    if (mode === "listening") return 0.82;
    if (mode === "presenting") return 0.96;
    if (mode === "talking") return 0.92;
    if (mode === "thinking") return 0.64;

    const recentlyActive =
      input.nowMs - input.userSpokeAtMs < PRESENCE_TUNING.recentInteractionMs ||
      input.nowMs - input.replyAtMs < PRESENCE_TUNING.recentInteractionMs;
    return recentlyActive ? 0.48 : 0.24;
  }

  private resolveAttention(input: PresenceInput): { target: AttentionTarget; offset: StagePoint } {
    if (input.nowMs - input.presentingAtMs < 4500) {
      return { target: "web_answer_box", offset: { x: 0.024, y: -0.012 } };
    }

    if (input.mode === "shutting_down") {
      return { target: "inward_focus", offset: { x: -0.01, y: -0.03 } };
    }

    if (input.mode === "thinking") {
      return { target: "inward_focus", offset: { x: -0.008, y: -0.02 } };
    }

    if (input.mode === "listening") {
      const overlayPull = input.overlays.transcriptOpen ? -0.01 : input.overlays.controlsOpen ? 0.01 : 0;
      return { target: "viewer_center", offset: { x: overlayPull, y: 0.006 } };
    }

    if (input.mode === "presenting") {
      return { target: "web_answer_box", offset: { x: 0.026, y: -0.012 } };
    }

    if (input.mode === "talking") {
      if (input.overlays.captionsVisible) {
        const phase = (Math.sin(input.nowMs * 0.0011) + 1) * 0.5;
        return {
          target: "captions_area",
          offset: { x: 0.004 * (phase - 0.5), y: -0.008 - phase * 0.004 },
        };
      }
      return { target: "viewer_center", offset: { x: 0.006, y: 0.008 } };
    }

    if (input.overlays.transcriptOpen) {
      return { target: "transcript_source", offset: { x: -0.01, y: 0 } };
    }

    if (input.overlays.controlsOpen) {
      return { target: "overlay_area", offset: { x: 0.01, y: 0.002 } };
    }

    return { target: "idle_neutral", offset: { x: 0.003 * Math.sin(input.nowMs * 0.0006), y: 0.002 } };
  }

  private idleMicroOffset(input: PresenceInput, idleBehavior: "none" | "wander" | "corner_rest"): StagePoint {
    if (input.mode !== "idle") return { x: 0, y: 0 };
    if (idleBehavior === "corner_rest") return { x: 0, y: 0 };
    if (this.engagement > 0.55) return { x: 0, y: 0 };
    if (input.overlays.shutdownVisible) return { x: 0, y: 0 };

    const x = Math.sin(input.nowMs * 0.00027) * PRESENCE_TUNING.idleMicroShiftAmplitude;
    const y = Math.cos(input.nowMs * 0.00023) * PRESENCE_TUNING.idleMicroShiftAmplitude * 0.4;
    return { x, y };
  }
}
