import type { MovementState, StagePoint } from "./movementController";
import { resolveStageZones, type OverlayVisibility, type StageBounds, type StageZoneName } from "./stageZones";
import { IdleBehaviorManager } from "./idleBehaviorManager";

export type AttentionTarget = "viewer_center" | "captions_area" | "overlay_area" | "transcript_source" | "web_answer_box" | "idle_neutral" | "inward_focus";
export type InteractionPresenceState = "idle" | "listening" | "thinking" | "speaking";
export type SemanticPresenceMode = "neutral" | "searching_browsing" | "processing_results" | "direct_answering" | "waiting_follow_up";

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
  searchHeadingRevealAtMs: number;
  searchFindingsRevealAtMs: number;
  searchSourcesRevealAtMs: number;
  searchSettledAtMs: number;
  semanticMode: SemanticPresenceMode;
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
  interactionPresenceState: InteractionPresenceState;
  semanticMode: SemanticPresenceMode;
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
  interactionPresence: {
    transitionMs: {
      listening: 300,
      thinking: 360,
      speaking: 220,
      idle: 380,
    },
    amplitudes: {
      idle: { tiltDeg: 0, yOffset: 0, forwardX: 0 },
      listening: { tiltDeg: 1.1, yOffset: -0.0024, forwardX: 0.0038 },
      thinking: { tiltDeg: 1.55, yOffset: -0.0012, forwardX: 0.0008 },
      speaking: { tiltDeg: 2.05, yOffset: -0.0029, forwardX: 0.0044 },
    },
    listening: {
      base: 0.9,
      swayHz: 0.135,
      swayScale: 0.11,
      settleDampen: 0.7,
    },
    thinking: {
      base: 0.62,
      pulseGapMs: { min: 980, max: 2200 },
      pulseDurationMs: { min: 260, max: 560 },
      pulseScale: { min: 0.09, max: 0.2 },
      tiltBiasDeg: 0.38,
      forwardReflectX: -0.0006,
    },
    speaking: {
      base: 0.9,
      rhythmHz: 1.08,
      rhythmScale: 0.25,
      secondaryHz: 0.54,
      secondaryScale: 0.09,
      antiBusyDampen: 0.74,
    },
  },
  speakingHoldMs: 760,
  listeningHoldMs: 580,
  presentationCues: {
    heading: {
      activeMs: 700,
      tiltDeg: 1.2,
      yOffset: -0.0018,
      forwardX: 0.0028,
      attentionX: 0.004,
      attentionY: -0.0015,
    },
    findings: {
      activeMs: 760,
      tiltDeg: 1.45,
      yOffset: -0.0022,
      forwardX: 0.0032,
      attentionX: 0.005,
      attentionY: -0.0018,
    },
    sources: {
      activeMs: 520,
      tiltDeg: 0.62,
      yOffset: -0.0008,
      forwardX: 0.0013,
      attentionX: 0.0022,
      attentionY: -0.0009,
    },
    settle: {
      holdMs: 460,
      fadeMs: 780,
    },
  },
  semanticPresence: {
    transitionMs: 360,
    searching_browsing: {
      tiltDeg: 0.24,
      yOffset: -0.0004,
      forwardX: 0.0007,
      idleMicroDampen: 0.45,
      movementWillingnessScale: 0.84,
      attentionX: 0.003,
      attentionY: -0.001,
    },
    processing_results: {
      tiltDeg: 0.3,
      yOffset: -0.0006,
      forwardX: 0.0004,
      idleMicroDampen: 0.62,
      movementWillingnessScale: 0.9,
      attentionX: 0.0022,
      attentionY: -0.0022,
    },
    direct_answering: {
      tiltDeg: 0,
      yOffset: 0,
      forwardX: 0,
      idleMicroDampen: 1,
      movementWillingnessScale: 1,
      attentionX: 0,
      attentionY: 0,
    },
    waiting_follow_up: {
      tiltDeg: 0.22,
      yOffset: -0.0003,
      forwardX: 0.0005,
      idleMicroDampen: 0.58,
      movementWillingnessScale: 0.78,
      attentionX: 0.0014,
      attentionY: 0.001,
    },
  },
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
  private interactionPresenceState: InteractionPresenceState = "idle";
  private interactionPose = { tiltDeg: 0, yOffset: 0, xOffset: 0 };
  private semanticMode: SemanticPresenceMode = "neutral";
  private semanticPose = { tiltDeg: 0, yOffset: 0, xOffset: 0 };
  private thinkingPulse = {
    active: false,
    startedAtMs: 0,
    durationMs: 0,
    amplitude: 0,
    direction: 1 as -1 | 1,
    nextAtMs: 0,
  };
  private posePulseSmoothed = {
    listening: 0.9,
    thinking: 0.62,
    speaking: 0.9,
  };

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
      overlays: input.overlays,
      currentPosition: input.currentPosition,
    });

    const baseTarget = idleBehavior.targetPosition ?? zones[this.zone];
    const interactionPresenceState = this.resolveInteractionPresenceState(input);
    const interactionOffset = this.resolveInteractionPoseOffset(interactionPresenceState, input);
    const semanticPresence = this.resolveSemanticPresenceOverlay(input);
    const presentationCueOffset = this.resolvePresentationCueOffset(input);
    const microOffset = this.idleMicroOffset(input, idleBehavior.idleBehavior, semanticPresence.idleMicroDampen);
    const proposedTarget: StagePoint = {
      x: clamp(baseTarget.x + microOffset.x + interactionOffset.xOffset + semanticPresence.poseOffset.xOffset + presentationCueOffset.xOffset, 0.08, 0.92),
      y: clamp(
        baseTarget.y + microOffset.y + idleBehavior.poseYOffset + interactionOffset.yOffset + semanticPresence.poseOffset.yOffset + presentationCueOffset.yOffset,
        0.28,
        0.82
      ),
    };

    const currentDelta = distance(proposedTarget, this.lastTarget);
    if (currentDelta > PRESENCE_TUNING.retargetDistanceThreshold || distance(input.currentPosition, this.lastTarget) > PRESENCE_TUNING.zoneSwitchDistance) {
      this.lastTarget = proposedTarget;
    }

    const attention = this.resolveAttention(input, {
      x: presentationCueOffset.attentionOffset.x + semanticPresence.attentionOffset.x,
      y: presentationCueOffset.attentionOffset.y + semanticPresence.attentionOffset.y,
    });
    this.focusOffset.x = smooth(this.focusOffset.x, attention.offset.x, PRESENCE_TUNING.focusSmoothing * 60, input.deltaSeconds);
    this.focusOffset.y = smooth(this.focusOffset.y, attention.offset.y, PRESENCE_TUNING.focusSmoothing * 60, input.deltaSeconds);

    return {
      preferredZone: this.zone,
      targetPosition: this.lastTarget,
      attentionTarget: attention.target,
      attentionOffset: { ...this.focusOffset },
      engagementLevel: this.engagement,
      movementWillingness:
        (idleBehavior.movementWillingness ?? this.movementWillingness(input.mode, input)) * semanticPresence.movementWillingnessScale,
      activityState: idleBehavior.activityState,
      idleBehavior: idleBehavior.idleBehavior,
      interactionPresenceState,
      semanticMode: semanticPresence.mode,
      poseTiltDeg: idleBehavior.poseTiltDeg + interactionOffset.tiltDeg + semanticPresence.poseOffset.tiltDeg + presentationCueOffset.tiltDeg,
      poseYOffset: idleBehavior.poseYOffset + interactionOffset.yOffset + semanticPresence.poseOffset.yOffset + presentationCueOffset.yOffset,
    };
  }

  private resolveSemanticPresenceOverlay(input: PresenceInput): {
    mode: SemanticPresenceMode;
    poseOffset: { tiltDeg: number; yOffset: number; xOffset: number };
    attentionOffset: StagePoint;
    movementWillingnessScale: number;
    idleMicroDampen: number;
  } {
    const mode = input.semanticMode;
    const transitionMs = PRESENCE_TUNING.semanticPresence.transitionMs;
    const ratePerSecond = 1000 / Math.max(120, transitionMs);
    if (mode !== this.semanticMode) {
      this.semanticMode = mode;
    }

    if (mode === "neutral") {
      this.semanticPose.tiltDeg = smooth(this.semanticPose.tiltDeg, 0, ratePerSecond, input.deltaSeconds);
      this.semanticPose.yOffset = smooth(this.semanticPose.yOffset, 0, ratePerSecond, input.deltaSeconds);
      this.semanticPose.xOffset = smooth(this.semanticPose.xOffset, 0, ratePerSecond, input.deltaSeconds);
      return {
        mode,
        poseOffset: { ...this.semanticPose },
        attentionOffset: { x: 0, y: 0 },
        movementWillingnessScale: 1,
        idleMicroDampen: 1,
      };
    }

    const tuning = PRESENCE_TUNING.semanticPresence[mode];
    this.semanticPose.tiltDeg = smooth(this.semanticPose.tiltDeg, tuning.tiltDeg, ratePerSecond, input.deltaSeconds);
    this.semanticPose.yOffset = smooth(this.semanticPose.yOffset, tuning.yOffset, ratePerSecond, input.deltaSeconds);
    this.semanticPose.xOffset = smooth(this.semanticPose.xOffset, tuning.forwardX, ratePerSecond, input.deltaSeconds);
    return {
      mode,
      poseOffset: { ...this.semanticPose },
      attentionOffset: { x: tuning.attentionX, y: tuning.attentionY },
      movementWillingnessScale: tuning.movementWillingnessScale,
      idleMicroDampen: tuning.idleMicroDampen,
    };
  }

  private resolvePresentationCueOffset(input: PresenceInput): { tiltDeg: number; yOffset: number; xOffset: number; attentionOffset: StagePoint } {
    if (input.mode !== "presenting_search_results") {
      return { tiltDeg: 0, yOffset: 0, xOffset: 0, attentionOffset: { x: 0, y: 0 } };
    }

    const cues = PRESENCE_TUNING.presentationCues;
    const headingProgress = cueProgress(input.nowMs, input.searchHeadingRevealAtMs, cues.heading.activeMs);
    const findingsProgress = cueProgress(input.nowMs, input.searchFindingsRevealAtMs, cues.findings.activeMs);
    const sourcesProgress = cueProgress(input.nowMs, input.searchSourcesRevealAtMs, cues.sources.activeMs);
    const settleFade = settleFadeFactor(input.nowMs, input.searchSettledAtMs, cues.settle.holdMs, cues.settle.fadeMs);
    return {
      tiltDeg: (cues.heading.tiltDeg * headingProgress + cues.findings.tiltDeg * findingsProgress + cues.sources.tiltDeg * sourcesProgress) * settleFade,
      yOffset: (cues.heading.yOffset * headingProgress + cues.findings.yOffset * findingsProgress + cues.sources.yOffset * sourcesProgress) * settleFade,
      xOffset: (cues.heading.forwardX * headingProgress + cues.findings.forwardX * findingsProgress + cues.sources.forwardX * sourcesProgress) * settleFade,
      attentionOffset: {
        x: (cues.heading.attentionX * headingProgress + cues.findings.attentionX * findingsProgress + cues.sources.attentionX * sourcesProgress) * settleFade,
        y: (cues.heading.attentionY * headingProgress + cues.findings.attentionY * findingsProgress + cues.sources.attentionY * sourcesProgress) * settleFade,
      },
    };
  }

  private resolveInteractionPresenceState(input: PresenceInput): InteractionPresenceState {
    if (input.mode === "talking" || input.mode === "presenting" || input.mode === "presenting_search_results") return "speaking";
    if (input.mode === "listening") return "listening";
    if (input.mode === "thinking") return "thinking";
    if (input.nowMs - input.replyAtMs < PRESENCE_TUNING.speakingHoldMs || input.nowMs - input.presentingAtMs < PRESENCE_TUNING.speakingHoldMs) {
      return "speaking";
    }
    if (input.nowMs - input.userSpokeAtMs < PRESENCE_TUNING.listeningHoldMs || input.nowMs - input.transcriptEventAtMs < PRESENCE_TUNING.listeningHoldMs) {
      return "listening";
    }
    return "idle";
  }

  private resolveInteractionPoseOffset(state: InteractionPresenceState, input: PresenceInput) {
    if (state !== this.interactionPresenceState) {
      this.interactionPresenceState = state;
      if (state !== "thinking") {
        this.thinkingPulse.active = false;
      } else if (this.thinkingPulse.nextAtMs === 0) {
        this.thinkingPulse.nextAtMs = input.nowMs + randomBetween(PRESENCE_TUNING.interactionPresence.thinking.pulseGapMs.min, PRESENCE_TUNING.interactionPresence.thinking.pulseGapMs.max);
      }
    }
    const amp = PRESENCE_TUNING.interactionPresence.amplitudes[state];
    const pulse = this.interactionPulse(state, input.nowMs, input.deltaSeconds);
    let targetTilt = amp.tiltDeg * pulse.tilt;
    const targetYOffset = amp.yOffset * pulse.body;
    let targetXOffset = amp.forwardX * pulse.forward;
    if (state === "thinking") {
      targetTilt += PRESENCE_TUNING.interactionPresence.thinking.tiltBiasDeg;
      targetXOffset += PRESENCE_TUNING.interactionPresence.thinking.forwardReflectX;
    }
    const transitionMs = PRESENCE_TUNING.interactionPresence.transitionMs[state];
    const ratePerSecond = 1000 / Math.max(80, transitionMs);
    this.interactionPose.tiltDeg = smooth(this.interactionPose.tiltDeg, targetTilt, ratePerSecond, input.deltaSeconds);
    this.interactionPose.yOffset = smooth(this.interactionPose.yOffset, targetYOffset, ratePerSecond, input.deltaSeconds);
    this.interactionPose.xOffset = smooth(this.interactionPose.xOffset, targetXOffset, ratePerSecond, input.deltaSeconds);
    return { ...this.interactionPose };
  }

  private interactionPulse(state: InteractionPresenceState, nowMs: number, deltaSeconds: number): { body: number; tilt: number; forward: number } {
    if (state === "idle") return { body: 0, tilt: 0, forward: 0 };
    if (state === "listening") {
      const listening = PRESENCE_TUNING.interactionPresence.listening;
      const raw = listening.base + (Math.sin(nowMs * listening.swayHz * 0.001 * Math.PI * 2) * 0.5 + 0.5) * listening.swayScale;
      this.posePulseSmoothed.listening = smooth(this.posePulseSmoothed.listening, raw, 6.2, deltaSeconds);
      const settled = this.posePulseSmoothed.listening;
      return {
        body: settled,
        tilt: settled * listening.settleDampen,
        forward: settled,
      };
    }
    if (state === "speaking") {
      const speaking = PRESENCE_TUNING.interactionPresence.speaking;
      const primary = (Math.sin(nowMs * speaking.rhythmHz * 0.001 * Math.PI * 2) * 0.5 + 0.5) * speaking.rhythmScale;
      const secondary = (Math.sin(nowMs * speaking.secondaryHz * 0.001 * Math.PI * 2 + Math.PI * 0.35) * 0.5 + 0.5) * speaking.secondaryScale;
      // Layering a slower secondary wave keeps speaking expressive without looking jittery.
      const raw = speaking.base + (primary + secondary) * speaking.antiBusyDampen;
      this.posePulseSmoothed.speaking = smooth(this.posePulseSmoothed.speaking, raw, 8.4, deltaSeconds);
      const rhythmic = this.posePulseSmoothed.speaking;
      return { body: rhythmic, tilt: rhythmic * 0.94, forward: rhythmic };
    }
    const thinking = PRESENCE_TUNING.interactionPresence.thinking;
    if (nowMs >= this.thinkingPulse.nextAtMs && !this.thinkingPulse.active) {
      this.thinkingPulse.active = true;
      this.thinkingPulse.startedAtMs = nowMs;
      this.thinkingPulse.durationMs = randomBetween(
        PRESENCE_TUNING.interactionPresence.thinking.pulseDurationMs.min,
        PRESENCE_TUNING.interactionPresence.thinking.pulseDurationMs.max
      );
      this.thinkingPulse.amplitude = randomBetween(
        PRESENCE_TUNING.interactionPresence.thinking.pulseScale.min,
        PRESENCE_TUNING.interactionPresence.thinking.pulseScale.max
      );
      this.thinkingPulse.direction = Math.random() > 0.5 ? 1 : -1;
    }
    if (!this.thinkingPulse.active) {
      this.posePulseSmoothed.thinking = smooth(this.posePulseSmoothed.thinking, thinking.base, 4.6, deltaSeconds);
      return { body: this.posePulseSmoothed.thinking, tilt: this.posePulseSmoothed.thinking, forward: this.posePulseSmoothed.thinking };
    }
    const t = clamp((nowMs - this.thinkingPulse.startedAtMs) / this.thinkingPulse.durationMs, 0, 1);
    if (t >= 1) {
      this.thinkingPulse.active = false;
      this.thinkingPulse.nextAtMs =
        nowMs + randomBetween(PRESENCE_TUNING.interactionPresence.thinking.pulseGapMs.min, PRESENCE_TUNING.interactionPresence.thinking.pulseGapMs.max);
      this.posePulseSmoothed.thinking = smooth(this.posePulseSmoothed.thinking, thinking.base, 4.4, deltaSeconds);
      return { body: this.posePulseSmoothed.thinking, tilt: this.posePulseSmoothed.thinking, forward: this.posePulseSmoothed.thinking };
    }
    const pulse = thinking.base + Math.sin(t * Math.PI) * this.thinkingPulse.amplitude * this.thinkingPulse.direction;
    this.posePulseSmoothed.thinking = smooth(this.posePulseSmoothed.thinking, pulse, 6, deltaSeconds);
    return {
      body: this.posePulseSmoothed.thinking,
      tilt: this.posePulseSmoothed.thinking,
      forward: this.posePulseSmoothed.thinking,
    };
  }

  private pickDesiredZone(input: PresenceInput): StageZoneName {
    const transcriptLocked = input.nowMs - input.transcriptEventAtMs < PRESENCE_TUNING.transcriptLockMs;
    if (input.mode === "shutting_down") return "shutdown_settle";
    if (input.mode === "listening") return "listening_anchor";
    if (input.mode === "presenting" || input.mode === "presenting_search_results") return "left_relaxed";
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
    if (mode === "presenting_search_results") return 0.06;
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
    if (mode === "presenting_search_results") return 0.98;
    if (mode === "talking") return 0.92;
    if (mode === "thinking") return 0.64;

    const recentlyActive =
      input.nowMs - input.userSpokeAtMs < PRESENCE_TUNING.recentInteractionMs ||
      input.nowMs - input.replyAtMs < PRESENCE_TUNING.recentInteractionMs;
    return recentlyActive ? 0.48 : 0.24;
  }

  private resolveAttention(input: PresenceInput, cueAttentionOffset: StagePoint): { target: AttentionTarget; offset: StagePoint } {
    if (input.nowMs - input.presentingAtMs < 4500) {
      return { target: "web_answer_box", offset: { x: 0.024 + cueAttentionOffset.x, y: -0.012 + cueAttentionOffset.y } };
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

    if (input.mode === "presenting" || input.mode === "presenting_search_results") {
      return { target: "web_answer_box", offset: { x: 0.03 + cueAttentionOffset.x, y: -0.013 + cueAttentionOffset.y } };
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

  private idleMicroOffset(input: PresenceInput, idleBehavior: "none" | "wander" | "corner_rest", dampen = 1): StagePoint {
    if (input.mode !== "idle") return { x: 0, y: 0 };
    if (idleBehavior === "corner_rest") return { x: 0, y: 0 };
    if (this.engagement > 0.55) return { x: 0, y: 0 };
    if (input.overlays.shutdownVisible) return { x: 0, y: 0 };

    const x = Math.sin(input.nowMs * 0.00027) * PRESENCE_TUNING.idleMicroShiftAmplitude * dampen;
    const y = Math.cos(input.nowMs * 0.00023) * PRESENCE_TUNING.idleMicroShiftAmplitude * 0.4 * dampen;
    return { x, y };
  }
}

function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function cueProgress(nowMs: number, cueAtMs: number, activeMs: number) {
  if (cueAtMs <= 0 || nowMs < cueAtMs) return 0;
  const t = clamp((nowMs - cueAtMs) / Math.max(120, activeMs), 0, 1);
  return Math.sin(t * Math.PI);
}

function settleFadeFactor(nowMs: number, settledAtMs: number, holdMs: number, fadeMs: number) {
  if (settledAtMs <= 0 || nowMs <= settledAtMs + holdMs) return 1;
  const t = clamp((nowMs - (settledAtMs + holdMs)) / Math.max(240, fadeMs), 0, 1);
  return 1 - t;
}
